/**
 * Login lifecycle guards for the OrcaRouter connect flow.
 *
 * Run from `OntiCards_Web` with:
 *   node --test --experimental-strip-types tests/orcarouter/connect.test.ts
 *
 * These are the behaviours a maintainer will ask about: can a stale response overwrite a newer
 * login, and does a back-forward-cache restore come back stuck "busy"?
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { createConnectController, type ConnectViewState } from '../../utils/orcarouter.ts'

function harness(overrides: Partial<Parameters<typeof createConnectController>[0]> = {}) {
  const states: ConnectViewState[] = []
  const cancels: { sessionId: string; reason: string }[] = []
  let releaseStart: (() => void) | null = null
  let startGate: Promise<void> | null = null
  let startCount = 0

  const deps = {
    startConnect: async () => {
      startCount += 1
      if (startGate) await startGate
      return { session_id: `session-${startCount}`, authorize_url: `https://www.orcarouter.ai/auth?state=s${startCount}`, status: 'pending' }
    },
    submitCode: async () => ({ api_key_masked: 'sk-orca…****' }),
    cancelConnect: (sessionId: string, reason: string) => {
      cancels.push({ sessionId, reason })
    },
    onUpdate: (state: ConnectViewState) => states.push({ ...state }),
    ...overrides,
  }

  return {
    controller: createConnectController(deps),
    states,
    cancels,
    latest: () => states[states.length - 1],
    blockStart: () => {
      startGate = new Promise<void>((resolve) => {
        releaseStart = resolve
      })
    },
    releaseStart: () => releaseStart?.(),
  }
}

test('starting a login opens the auth origin and waits for the code', async () => {
  const h = harness()
  await h.controller.start()
  const state = h.latest()
  assert.equal(state.phase, 'awaiting_code')
  assert.equal(state.busy, false)
  assert.ok(state.authorizeUrl!.startsWith('https://www.orcarouter.ai/auth?'))
  assert.equal(state.sessionId, 'session-1')
})

test('submitting the code reaches the connected state and shows a masked key', async () => {
  const h = harness()
  await h.controller.start()
  await h.controller.submitCode('fake-code')
  const state = h.latest()
  assert.equal(state.phase, 'connected')
  assert.equal(state.busy, false)
  assert.equal(state.maskedKey, 'sk-orca…****')
})

test('an empty code is refused without disturbing the session', async () => {
  const h = harness()
  await h.controller.start()
  await h.controller.submitCode('   ')
  assert.equal(h.latest().phase, 'error')
  assert.equal(h.latest().sessionId, 'session-1')
})

test('a failure surfaces an actionable error and clears busy', async () => {
  const h = harness({
    startConnect: async () => {
      throw new Error('授权服务不可用')
    },
  })
  await h.controller.start()
  assert.equal(h.latest().phase, 'error')
  assert.equal(h.latest().busy, false)
  assert.equal(h.latest().error, '授权服务不可用')
})

test('explicit cancel releases busy state and tells the server', async () => {
  const h = harness()
  await h.controller.start()
  h.controller.cancel()
  assert.equal(h.latest().phase, 'idle')
  assert.equal(h.latest().busy, false)
  assert.deepEqual(h.cancels, [{ sessionId: 'session-1', reason: 'cancelled' }])
})

test('a stale success cannot overwrite a newer login', async () => {
  const h = harness()
  h.blockStart()
  const first = h.controller.start() // in flight, blocked
  // A second attempt supersedes the first before it resolves.
  h.releaseStart()
  h.blockStart()
  const second = h.controller.start()
  h.releaseStart()
  await Promise.all([first, second])

  const state = h.latest()
  assert.equal(state.sessionId, 'session-2')
  assert.equal(state.phase, 'awaiting_code')
})

test('a stale failure cannot overwrite a newer login', async () => {
  let attempt = 0
  const h = harness({
    startConnect: async () => {
      attempt += 1
      if (attempt === 1) throw new Error('first attempt failed')
      return { session_id: 'session-2', authorize_url: 'https://www.orcarouter.ai/auth?state=s2', status: 'pending' }
    },
  })
  const first = h.controller.start()
  const second = h.controller.start()
  await Promise.all([first, second])
  const state = h.latest()
  assert.equal(state.phase, 'awaiting_code')
  assert.equal(state.sessionId, 'session-2')
  assert.equal(state.error, null)
})

test('a late exchange response after cancel does not resurrect the session', async () => {
  let resolveSubmit: ((v: { api_key_masked: string }) => void) | null = null
  const h = harness({
    submitCode: () =>
      new Promise((resolve) => {
        resolveSubmit = resolve
      }),
  })
  await h.controller.start()
  const pending = h.controller.submitCode('fake-code')
  h.controller.cancel()
  resolveSubmit!({ api_key_masked: 'sk-orca…****' })
  await pending

  const state = h.latest()
  assert.equal(state.phase, 'idle')
  assert.equal(state.maskedKey, null)
})

test('pagehide clears busy and hint synchronously and cancels the server attempt', async () => {
  const h = harness()
  await h.controller.start()
  h.controller.handlePageHide()

  const state = h.controller.getState()
  assert.equal(state.busy, false)
  assert.equal(state.hint, null)
  assert.equal(state.phase, 'idle')
  assert.deepEqual(h.cancels, [{ sessionId: 'session-1', reason: 'pagehide' }])
})

test('a second login can start after pagehide without remounting', async () => {
  const h = harness()
  await h.controller.start()
  h.controller.handlePageHide()
  // No remount: the same controller instance is reused.
  await h.controller.start()
  const state = h.latest()
  assert.equal(state.phase, 'awaiting_code')
  assert.equal(state.sessionId, 'session-2')
  assert.equal(state.busy, false)
})

test('pagehide releases a login that is still starting', async () => {
  const h = harness()
  h.blockStart()
  const pending = h.controller.start()
  h.controller.handlePageHide()
  assert.equal(h.controller.getState().busy, false)
  h.releaseStart()
  await pending
  // The blocked start resolved after pagehide and must not have re-armed the flow.
  assert.equal(h.controller.getState().busy, false)
  assert.equal(h.controller.getState().sessionId, null)
})

test('generation increases monotonically so late responses are identifiable', async () => {
  const h = harness()
  await h.controller.start()
  const first = h.controller.getState().generation
  h.controller.handlePageHide()
  await h.controller.start()
  assert.ok(h.controller.getState().generation > first)
})
