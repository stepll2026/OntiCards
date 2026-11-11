import test from 'node:test'
import assert from 'node:assert/strict'
import { getCleanupError, finishCancelledExtraction } from '../utils/vectorCleanup.ts'

test('success and zero deleted objects are not failures', () => {
  assert.equal(getCleanupError({ code: 200, data: { weaviate_deleted: 0 } }), null)
  assert.equal(getCleanupError({ code: 200, data: { cleanup_complete: true } }), null)
})
test('legacy success cannot hide vector or cleanup failure', () => {
  assert.match(getCleanupError({ code: 200, msg: '删除成功', data: { weaviate_deleted: false } }), /清理/)
  assert.match(getCleanupError({ code: 200, result: { cleanup_complete: false } }), /清理/)
})
test('API and HTTP failures never become success', () => {
  assert.equal(getCleanupError({ code: 502, msg: '清理失败' }), '清理失败')
  assert.ok(getCleanupError({ code: 200 }, false))
})
test('cancellation waits for cleanup acknowledgement', async () => {
  let release
  let completed = false
  const pending = finishCancelledExtraction(() => new Promise(resolve => { release = resolve }), () => assert.fail('unexpected warning'))
    .then(result => { completed = true; return result })
  await Promise.resolve()
  assert.equal(completed, false)
  release({ code: 200, data: { cleanup_complete: true } })
  assert.equal((await pending).code, 499)
})
test('cleanup failure after cancellation is visible even if modal closed', async () => {
  const warnings = []
  const result = await finishCancelledExtraction(async () => ({ code: 200, data: { weaviate_deleted: false } }), text => warnings.push(text))
  assert.equal(result.code, 502)
  assert.equal(warnings.length, 1)
  assert.match(warnings[0], /清理/)
})
test('network failure after cancellation stays actionable', async () => {
  const warnings = []
  const result = await finishCancelledExtraction(async () => { throw new Error('offline') }, text => warnings.push(text))
  assert.equal(result.code, 502)
  assert.equal(warnings.length, 1)
})

// Integration guards: keep the helper wired into each destructive handler,
// rather than accidentally applying it only to the quick connection check.
import { readFileSync } from 'node:fs'
const workspacePage = readFileSync(new URL('../app/[lng]/(newLayout)/workspaces/WorkspacesPage.tsx', import.meta.url), 'utf8')
for (const [name, end] of [['confirmDeleteDataSource', 'cancelDelete'], ['handleRefresh', null]]) {
  test(`${name} declares and checks cleanup errors before showing success`, () => {
    const start = workspacePage.indexOf(`const ${name} =`)
    assert.ok(start >= 0)
    const body = workspacePage.slice(start, end ? workspacePage.indexOf(`const ${end} =`, start) : workspacePage.indexOf('\n  };', start))
    assert.match(body, /const cleanupError = getCleanupError\(data, response\.ok\);\s*if \(!cleanupError\)/)
    assert.match(body, /message\.error\(cleanupError\)/)
    assert.doesNotMatch(body, /if \(data\.code === 200\)/)
  })
}
test('quick connection testing is not changed into a cleanup operation', () => {
  const body = workspacePage.slice(workspacePage.indexOf('const handleTestConnection ='), workspacePage.indexOf('const handleDeleteDataSource ='))
  assert.doesNotMatch(body, /getCleanupError/)
})
test('extract cancellation awaits the cleanup helper and displays its warning', () => {
  const source = readFileSync(new URL('../api/datasource.ts', import.meta.url), 'utf8')
  assert.match(source, /return await finishCancelledExtraction\(\s*\(\) => cancelExtractSchema\(requestId, config\),\s*warning => \{ message\.warning\(warning, 8\) \}/)
})
