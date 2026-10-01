/**
 * OrcaRouter frontend rules, and their parity with the backend contract.
 *
 * Run from `OntiCards_Web` with:
 *   node --test --experimental-strip-types tests/orcarouter/orcarouter.test.ts
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

import {
  MODEL_CLASS_CAPABILITY,
  MODEL_CLASS_PATHS,
  ORCAROUTER_API_BASE,
  ORCAROUTER_AUTH_BASE,
  ORCAROUTER_AUTH_METHODS,
  ORCAROUTER_KEY_DASHBOARD_URL,
  ORCAROUTER_MODEL_TYPE,
  authMethodLabel,
  filterCatalog,
  isLoopbackUrl,
  isModelStillCompatible,
  isOrcaRouterModelType,
  maskKey,
  resolveModelUrl,
} from '../../utils/orcarouter.ts'

const HERE = dirname(fileURLToPath(import.meta.url))

const BACKEND_FILES = {
  bases: resolve(HERE, '../../../OntiCards_Api/core/orcarouter/bases.py'),
  catalog: resolve(HERE, '../../../OntiCards_Api/core/orcarouter/catalog.py'),
  credentials: resolve(HERE, '../../../OntiCards_Api/core/orcarouter/credentials.py'),
}

const readBackend = (key: string): string => {
  const path = BACKEND_FILES[key as keyof typeof BACKEND_FILES]
  assert.ok(existsSync(path), `backend source not found at ${path}`)
  return readFileSync(path, 'utf8')
}

const CATALOG = [
  { id: 'deepseek/deepseek-v4-flash', name: 'DS', supported_endpoint_types: ['openai', 'openai-response'], input_modalities: ['text'], context_length: 1048576 },
  { id: 'deepseek/deepseek-v4.1-flash', name: 'DS VL', supported_endpoint_types: ['openai', 'anthropic'], input_modalities: ['text', 'image'] },
  { id: 'openai/gpt-5.5', name: 'GPT', supported_endpoint_types: ['openai', 'openai-response'], input_modalities: ['text', 'image'], reasoning: true, reasoning_efforts: ['low', 'medium', 'high', 'xhigh'], context_length: 400000 },
  { id: 'orcarouter/auto', name: 'Auto', supported_endpoint_types: ['openai', 'anthropic', 'gemini'], input_modalities: ['text'] },
  { id: 'vendor/text-to-image', name: 'IMG', supported_endpoint_types: ['image-generation'], input_modalities: [] },
  { id: 'vendor/video-maker', name: 'VID', supported_endpoint_types: ['openai-video'], input_modalities: [] },
  { id: 'vendor/reranker', name: 'RR', supported_endpoint_types: ['jina-rerank'], input_modalities: [] },
  { id: 'vendor/embedder', name: 'EMB', supported_endpoint_types: ['embeddings'], input_modalities: [] },
]

const ids = (models: { id: string }[]) => models.map((m) => m.id).sort()

test('both authentication choices are registered and labelled distinctly', () => {
  assert.deepEqual(
    ORCAROUTER_AUTH_METHODS.map((m) => m.id),
    ['api_key', 'pkce'],
  )
  const labels = ORCAROUTER_AUTH_METHODS.map((m) => m.label)
  assert.deepEqual(labels, ['OrcaRouter - API', 'OrcaRouter - Auth'])
  assert.equal(new Set(labels).size, 2)
  assert.equal(authMethodLabel('api_key'), 'OrcaRouter - API')
  assert.equal(authMethodLabel('pkce'), 'OrcaRouter - Auth')
  assert.equal(authMethodLabel(null), '')
})

test('origins are the documented pair and never derived from one another', () => {
  assert.equal(ORCAROUTER_AUTH_BASE, 'https://www.orcarouter.ai')
  assert.equal(ORCAROUTER_API_BASE, 'https://api.orcarouter.ai/v1')
  assert.ok(ORCAROUTER_KEY_DASHBOARD_URL.startsWith(ORCAROUTER_AUTH_BASE))
  assert.notEqual(ORCAROUTER_API_BASE.replace('/v1', ''), ORCAROUTER_AUTH_BASE)
})

test('chat filter drops models without text endpoints and non-text dedicated models', () => {
  const result = ids(filterCatalog(CATALOG, 'chat'))
  assert.deepEqual(result, ['deepseek/deepseek-v4-flash', 'deepseek/deepseek-v4.1-flash', 'openai/gpt-5.5', 'orcarouter/auto'])
  assert.ok(!result.includes('vendor/text-to-image'))
  assert.ok(!result.includes('vendor/video-maker'))
  assert.ok(!result.includes('vendor/reranker'))
  assert.ok(!result.includes('vendor/embedder'))
})

test('the multimodal filter is fail-closed', () => {
  // Only models that explicitly declare image input survive.
  assert.deepEqual(ids(filterCatalog(CATALOG, 'chat', ['image'])), [
    'deepseek/deepseek-v4.1-flash',
    'openai/gpt-5.5',
  ])
  // A model with no declared modality cannot slip in, even if its name suggests vision.
  assert.ok(!ids(filterCatalog(CATALOG, 'chat', ['image'])).includes('orcarouter/auto'))
})

test('non-chat capabilities are matched exactly', () => {
  assert.deepEqual(ids(filterCatalog(CATALOG, 'embedding')), ['vendor/embedder'])
  assert.deepEqual(ids(filterCatalog(CATALOG, 'image')), ['vendor/text-to-image'])
  assert.deepEqual(ids(filterCatalog(CATALOG, 'video')), ['vendor/video-maker'])
  assert.deepEqual(ids(filterCatalog(CATALOG, 'rerank')), ['vendor/reranker'])
  // An unknown capability fails closed rather than showing everything.
  assert.deepEqual(filterCatalog(CATALOG, 'telepathy' as never), [])
})

test('model classes map onto capabilities', () => {
  assert.deepEqual(MODEL_CLASS_CAPABILITY, { base: 'chat', embedding: 'embedding', rerank: 'rerank' })
})

test('reasoning and context metadata survive filtering', () => {
  const gpt = filterCatalog(CATALOG, 'chat').find((m) => m.id === 'openai/gpt-5.5')
  assert.ok(gpt)
  assert.equal(gpt.reasoning, true)
  assert.deepEqual(gpt.reasoning_efforts, ['low', 'medium', 'high', 'xhigh'])
  assert.equal(gpt.context_length, 400000)
})

test('a model that becomes incompatible is detected so the selection can be cleared', () => {
  assert.ok(isModelStillCompatible('openai/gpt-5.5', CATALOG, 'chat', ['image']))
  // The same model is fine for text but a text-only model is not fine for an image attachment.
  assert.ok(isModelStillCompatible('deepseek/deepseek-v4-flash', CATALOG, 'chat'))
  assert.equal(isModelStillCompatible('deepseek/deepseek-v4-flash', CATALOG, 'chat', ['image']), false)
  // A model that vanished from the catalog is no longer compatible.
  assert.equal(isModelStillCompatible('gone/model', CATALOG, 'chat'), false)
})

test('url resolution preserves other providers and derives OrcaRouter endpoints', () => {
  // Non-OrcaRouter rows keep the stored full endpoint verbatim.
  assert.equal(resolveModelUrl('doubao', 'base', 'https://ark.example/v3/chat/completions'), 'https://ark.example/v3/chat/completions')
  // OrcaRouter rows store a base URL; the endpoint is derived.
  assert.equal(resolveModelUrl(ORCAROUTER_MODEL_TYPE, 'base', ORCAROUTER_API_BASE), 'https://api.orcarouter.ai/v1/chat/completions')
  assert.equal(resolveModelUrl('OrcaRouter', 'embedding', ORCAROUTER_API_BASE), 'https://api.orcarouter.ai/v1/embeddings')
  assert.equal(resolveModelUrl('orcarouter', 'rerank', 'https://self.example/v1'), 'https://self.example/v1/rerank')
  // An empty value falls back to the default inference base.
  assert.equal(resolveModelUrl('orcarouter', 'base', ''), 'https://api.orcarouter.ai/v1/chat/completions')
  // A full endpoint is not doubled.
  assert.equal(resolveModelUrl('orcarouter', 'base', 'https://api.orcarouter.ai/v1/chat/completions'), 'https://api.orcarouter.ai/v1/chat/completions')
})

test('provider identity matching is exact and does not catch OpenRouter', () => {
  assert.ok(isOrcaRouterModelType('orcarouter'))
  assert.ok(isOrcaRouterModelType('OrcaRouter'))
  assert.ok(!isOrcaRouterModelType('openrouter'))
  assert.ok(!isOrcaRouterModelType(''))
  assert.ok(!isOrcaRouterModelType(null))
})

test('key masking never reveals key material', () => {
  const key = 'sk-orca-abcdefghijklmnopqrstuvwxyz'
  const masked = maskKey(key)
  assert.ok(!masked.includes('abcdefghij'))
  assert.equal(maskKey(''), '')
  assert.equal(maskKey(null), '')
  assert.equal(maskKey('short'), '*****')
})

test('loopback detection follows the http:// policy', () => {
  assert.ok(isLoopbackUrl('http://127.0.0.1:8080/v1'))
  assert.ok(isLoopbackUrl('http://localhost:3000'))
  assert.ok(isLoopbackUrl('http://[::1]:9000'))
  assert.ok(!isLoopbackUrl('https://api.orcarouter.ai/v1'))
  assert.ok(!isLoopbackUrl('http://api.example.com/v1'))
})

test('frontend and backend agree on the capability and endpoint tables', () => {
  const catalogSrc = readBackend('catalog')
  const basesSrc = readBackend('bases')

  // Endpoint paths must match MODEL_CLASS_PATHS in bases.py.
  for (const [modelClass, path] of Object.entries(MODEL_CLASS_PATHS)) {
    const pattern = new RegExp(`"${modelClass}":\\s*"${path.replace(/\//g, '\\/')}"`)
    assert.ok(pattern.test(basesSrc), `bases.py MODEL_CLASS_PATHS missing ${modelClass}: ${path}`)
  }

  // Model-class -> capability mapping must match MODEL_CLASS_CAPABILITY in catalog.py.
  for (const [modelClass, capability] of Object.entries(MODEL_CLASS_CAPABILITY)) {
    const pattern = new RegExp(`"${modelClass}":\\s*"${capability}"`)
    assert.ok(pattern.test(catalogSrc), `catalog.py MODEL_CLASS_CAPABILITY missing ${modelClass}: ${capability}`)
  }

  // The text / non-text endpoint type sets must match.
  const textMatch = catalogSrc.match(/TEXT_ENDPOINT_TYPES = frozenset\(\{([^}]*)\}\)/)
  assert.ok(textMatch, 'TEXT_ENDPOINT_TYPES not found in catalog.py')
  for (const type of ['openai', 'openai-response', 'anthropic', 'gemini']) {
    assert.ok(textMatch![1].includes(`"${type}"`), `catalog.py TEXT_ENDPOINT_TYPES missing ${type}`)
  }

  const nonTextMatch = catalogSrc.match(/NON_TEXT_ENDPOINT_TYPES = frozenset\(\s*\{([^}]*)\}/)
  assert.ok(nonTextMatch, 'NON_TEXT_ENDPOINT_TYPES not found in catalog.py')
  for (const type of ['image-generation', 'openai-video', 'jina-rerank', 'embeddings']) {
    assert.ok(nonTextMatch![1].includes(`"${type}"`), `catalog.py NON_TEXT_ENDPOINT_TYPES missing ${type}`)
  }

  // Public origins must match.
  assert.ok(basesSrc.includes('DEFAULT_AUTH_BASE = "https://www.orcarouter.ai"'))
  assert.ok(basesSrc.includes('DEFAULT_API_BASE = "https://api.orcarouter.ai/v1"'))
  assert.ok(basesSrc.includes('AUTHORIZE_PATH = "/auth"'))
  assert.ok(basesSrc.includes('EXCHANGE_PATH = "/api/v1/auth/keys"'))

  // Both credential sources exist on the backend seam.
  const credentialsSrc = readBackend('credentials')
  assert.ok(credentialsSrc.includes('SOURCE_API_KEY = "api_key"'))
  assert.ok(credentialsSrc.includes('SOURCE_PKCE = "pkce"'))
})
