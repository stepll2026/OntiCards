// Run against a built Web app. All API data and credentials are synthetic.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright')
const assert = require('node:assert/strict')
const path = require('node:path')

;(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  const user = { id: 'fixture-admin', name: 'test', role: 'admin', status: 'normal' }
  let models = [{ id: 'base-fixture', model_name: 'existing-model', model_type: 'Qwen', model_class: 'base',
    model_api_key: 'fixture-key', url: 'https://service.example/v1/chat/completions' },
    { id: 'rerank-fixture', model_name: 'local-rerank', model_type: 'local', model_class: 'rerank',
      model_api_key: null, url: 'http://localhost:8080/v1' }]
  const pending = [], probes = [], saved = []
  await page.addInitScript(value => {
    localStorage.setItem('console_token', 'fixture-token')
    localStorage.setItem('userInfo', JSON.stringify(value))
  }, user)
  await page.route('**/console/api/**', async route => {
    const request = route.request()
    const pathname = new URL(request.url()).pathname
    if (pathname.endsWith('/model_config/test')) { probes.push(route); return }
    if (pathname.endsWith('/model_config/models')) { pending.push(route); return }
    let data = []
    if (pathname.endsWith('/user')) data = user
    if (pathname.endsWith('/model_config')) {
      if (request.method() === 'GET') data = models
      else {
        const body = request.postDataJSON()
        saved.push(body)
        const record = { ...body, id: body.id || 'new-fixture' }
        models = [...models.filter(item => item.id !== record.id), record]
        data = { id: record.id }
      }
    }
    await route.fulfill({ json: { code: 200, data, result: data } })
  })
  const next = async (queue = pending) => {
    const deadline = Date.now() + 10000
    while (!queue.length && Date.now() < deadline) await page.waitForTimeout(50)
    assert.ok(queue.length, 'model request should be pending')
    return queue.shift()
  }
  const catalog = async (route, ids) => route.fulfill({ json: { code: 200, data: {
    models: ids.map(id => ({ id })), partial: false, message: '',
  } } })
  try {
    await page.goto(`${process.env.MODEL_TEST_WEB_URL || 'http://127.0.0.1:3117'}/en/settings?tab=model`, { waitUntil: 'domcontentloaded' })
    await page.getByRole('heading', { name: '模型配置', exact: true }).waitFor()
    await page.getByTitle('编辑', { exact: true }).first().click()
    const url = page.locator('#model-service-url'), key = page.locator('#model-service-key'), name = page.locator('#model-service-name')
    assert.equal(await url.inputValue(), 'https://service.example/v1/chat/completions')
    assert.equal(await name.inputValue(), 'existing-model')
    await url.fill('https://service.example/v1')
    await page.getByRole('button', { name: '读取模型', exact: true }).click()
    const first = await next()
    assert.deepEqual(first.request().postDataJSON(), { url: 'https://service.example/v1', model_api_key: 'fixture-key', api_protocol: 'auto' })
    await catalog(first, ['chat-alpha', 'chat-beta', 'existing-model'])
    await page.getByText('已读取 3 个模型，可搜索选择或手动填写。', { exact: true }).waitFor()
    await name.fill('chat-al')
    await page.locator('.ant-select-item-option-content').filter({ has: page.getByText('chat-alpha', { exact: true }) }).click()
    assert.equal(await name.inputValue(), 'chat-alpha')
    const protocol = page.locator('#model-service-protocol')
    assert.equal(await protocol.inputValue(), 'auto')
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    const probe = await next(probes)
    assert.equal(probe.request().postDataJSON().model_class, 'base')
    assert.equal(probe.request().postDataJSON().api_protocol, 'auto')
    await probe.fulfill({ json: { code: 200, data: { success: true, model_class: 'base', protocol: 'openai', latency_ms: 12 } } })
    await page.getByTestId('model-test-result').filter({ hasText: '测试通过' }).waitFor()
    await page.getByRole('button', { name: '测试流式对话', exact: true }).click()
    const streamProbe = await next(probes)
    assert.equal(streamProbe.request().postDataJSON().test_stream, true)
    // A changed model invalidates even a successful late response.
    await name.fill('temporary-custom')
    await streamProbe.fulfill({ json: { code: 200, data: { success: true, model_class: 'base', protocol: 'openai', stream: true, latency_ms: 22 } } })
    await page.waitForTimeout(100)
    assert.ok(!(await page.getByTestId('model-test-result').innerText()).includes('测试通过'))
    await name.fill('chat-alpha')
    if (process.env.MODEL_TEST_ARTIFACTS) await page.screenshot({ path: path.join(process.env.MODEL_TEST_ARTIFACTS, 'model-config-ui.png'), fullPage: true })
    await page.getByRole('button', { name: '保存配置', exact: true }).click()
    await page.getByRole('heading', { name: '编辑模型', exact: true }).waitFor({ state: 'hidden' })
    assert.equal(saved[0].model_name, 'chat-alpha')
    assert.equal(saved[0].url, 'https://service.example/v1')

    // Manual names can be saved without reading a provider catalog or supplying a key.
    await page.getByRole('button', { name: '添加配置', exact: true }).first().click()
    await url.fill('http://localhost:11434/v1')
    await name.fill('private-embedding-model')
    await page.getByRole('button', { name: '保存配置', exact: true }).click()
    await page.getByRole('heading', { name: '新增向量化嵌入模型', exact: true }).waitFor({ state: 'hidden' })
    assert.equal(saved[1].model_name, 'private-embedding-model')
    assert.equal(saved[1].model_api_key, '')
    assert.equal(saved[1].model_class, 'embedding')
    assert.equal(pending.length, 0)

    await page.getByTitle('编辑', { exact: true }).first().click()
    await page.getByRole('button', { name: '读取模型', exact: true }).click()
    await (await next()).fulfill({ status: 502, json: { code: 502, msg: '服务商鉴权失败，请核对 API Key 和接口地址；也可手动填写模型名称。' } })
    await page.getByRole('alert').filter({ hasText: '服务商鉴权失败' }).waitFor()
    await name.fill('custom-chat-id')
    assert.equal(await page.getByRole('button', { name: '保存配置', exact: true }).isEnabled(), true)

    // Changing credentials/address invalidates previous options and in-flight reads.
    await page.getByRole('button', { name: '读取模型', exact: true }).click()
    const old = await next()
    await url.fill('https://new-service.example/v1')
    await key.fill('new-fixture-key')
    await page.getByRole('button', { name: '读取模型', exact: true }).click()
    await catalog(await next(), ['new-provider-model'])
    await page.getByText('已读取 1 个模型，可搜索选择或手动填写。', { exact: true }).waitFor()
    await catalog(old, ['stale-one', 'stale-two'])
    await page.waitForTimeout(100)
    assert.equal(await name.inputValue(), 'custom-chat-id')
    await name.fill('new-provider')
    await page.locator('.ant-select-item-option-content').filter({ has: page.getByText('new-provider-model', { exact: true }) }).waitFor()
    assert.equal(await page.getByText('已读取 2 个模型，可搜索选择或手动填写。', { exact: true }).count(), 0)
    await name.fill('custom-chat-id')
    await page.getByRole('button', { name: '保存配置', exact: true }).click()
    await page.getByRole('heading', { name: '编辑模型', exact: true }).waitFor({ state: 'hidden' })
    assert.equal(saved[2].model_name, 'custom-chat-id')
    await page.getByTitle('编辑', { exact: true }).last().click()
    assert.equal(await key.inputValue(), '')
    await name.fill('local-rerank-v2')
    await page.getByRole('button', { name: '保存配置', exact: true }).click()
    await page.getByRole('heading', { name: '编辑模型', exact: true }).waitFor({ state: 'hidden' })
    assert.equal(saved[3].model_api_key, '')
    // Capability filtering keeps unknown deployments and offers all purposes explicitly.
    await page.getByTitle('编辑', { exact: true }).nth(1).click()
    await url.fill('https://model-provider.example/api/v1')
    await protocol.selectOption('dashscope')
    await page.getByRole('button', { name: '读取模型', exact: true }).click()
    const typed = await next()
    assert.equal(typed.request().postDataJSON().api_protocol, 'dashscope')
    await typed.fulfill({ json: { code: 200, data: { partial: false, message: '', models: [
      { id: 'chat-known', capabilities: ['base'], capability_source: 'metadata' },
      { id: 'vector-known', capabilities: ['embedding'], capability_source: 'metadata' },
      { id: 'rank-known', capabilities: ['rerank'], capability_source: 'name' },
      { id: 'private-unknown', capabilities: [], capability_source: 'unknown' },
    ] } } })
    await page.getByText('已读取 4 个模型，可搜索选择或手动填写。', { exact: true }).waitFor()
    await name.fill('')
    await name.click()
    await page.locator('.ant-select-item-option-content').filter({ has: page.getByText('vector-known', { exact: true }) }).waitFor()
    assert.equal(await page.locator('.ant-select-item-option-content').filter({ has: page.getByText('chat-known', { exact: true }) }).count(), 0)
    await page.locator('.ant-select-item-option-content').filter({ has: page.getByText('private-unknown', { exact: true }) }).waitFor()
    await page.getByRole('checkbox', { name: /显示所有用途/ }).check()
    await name.fill('rank-known')
    await page.locator('.ant-select-item-option-content').filter({ has: page.getByText('rank-known', { exact: true }) }).click()
    await page.getByTestId('model-purpose').filter({ hasText: '可能与当前用途不匹配' }).waitFor()
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    await (await next(probes)).fulfill({ status: 502, json: { code: 502, msg: '未返回有效的向量，请确认选择的是文本向量模型及对应接口。' } })
    await page.getByTestId('model-test-result').filter({ hasText: '未返回有效的向量' }).waitFor()
    assert.equal(await page.getByRole('button', { name: '保存配置', exact: true }).isEnabled(), true)
    await name.fill('private-embedding-model')
    await page.locator('#model-service-dimensions').fill('256')
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    const vectorProbe = await next(probes)
    assert.equal(vectorProbe.request().postDataJSON().embedding_dimensions, 256)
    await vectorProbe.fulfill({ json: { code: 200, data: { success: true, model_class: 'embedding', protocol: 'dashscope', dimensions: 256, latency_ms: 40 } } })
    await page.getByTestId('model-test-result').filter({ hasText: '返回 256 维向量' }).waitFor()
    await page.getByTestId('model-purpose').filter({ hasText: '已通过向量化嵌入模型的调用测试' }).waitFor()
    await page.getByRole('heading', { name: '编辑模型', exact: true }).click()
    await page.locator('.ant-select-dropdown:visible').waitFor({ state: 'hidden' })
    await page.waitForTimeout(250)
    if (process.env.MODEL_TEST_ARTIFACTS) await page.screenshot({ path: path.join(process.env.MODEL_TEST_ARTIFACTS, 'model-protocol-ui.png'), fullPage: true })
    await page.getByRole('button', { name: '保存配置', exact: true }).click()
    await page.getByRole('heading', { name: '编辑模型', exact: true }).waitFor({ state: 'hidden' })
    assert.equal(saved[4].api_protocol, 'dashscope')
    assert.equal(saved[4].embedding_dimensions, 256)
    await page.getByTitle('编辑', { exact: true }).nth(1).click()
    assert.equal(await protocol.inputValue(), 'dashscope')
    assert.equal(await page.locator('#model-service-dimensions').inputValue(), '256')
    // Native protocols expose only the applicable roles and persist extra settings.
    assert.equal(await protocol.locator('option[value="anthropic"]').isDisabled(), true)
    await protocol.selectOption('ark')
    await name.fill('ep-fixture-multimodal')
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    const arkProbe = await next(probes)
    assert.equal(arkProbe.request().postDataJSON().api_protocol, 'ark')
    await arkProbe.fulfill({ json: { code: 200, data: { success: true, model_class: 'embedding', protocol: 'ark', dimensions: 256, latency_ms: 10 } } })
    await page.getByTestId('model-test-result').filter({ hasText: '豆包多模态向量' }).waitFor()
    await page.getByRole('button', { name: '取消', exact: true }).click()
    await page.getByTitle('编辑', { exact: true }).last().click()
    await protocol.selectOption('viking')
    await page.getByLabel('Secret Access Key', { exact: true }).fill('fixture-sk')
    await page.getByLabel('Access Key ID', { exact: true }).fill('fixture-ak')
    await page.getByLabel('地域', { exact: true }).fill('cn-beijing')
    await page.getByLabel('接入点 ID（可选）', { exact: true }).fill('ep-fixture')
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    const vikingProbe = await next(probes)
    assert.deepEqual(vikingProbe.request().postDataJSON().api_options, { access_key_id: 'fixture-ak', region: 'cn-beijing', endpoint_id: 'ep-fixture' })
    await vikingProbe.fulfill({ json: { code: 200, data: { success: true, model_class: 'rerank', protocol: 'viking', ranked_documents: 2, latency_ms: 10 } } })
    await page.getByTestId('model-test-result').filter({ hasText: 'Viking' }).waitFor()
    if (process.env.MODEL_TEST_ARTIFACTS) await page.screenshot({ path: path.join(process.env.MODEL_TEST_ARTIFACTS, 'model-viking-ui.png'), fullPage: true })
    await page.getByRole('button', { name: '保存配置', exact: true }).click()
    await page.getByRole('heading', { name: '编辑模型', exact: true }).waitFor({ state: 'hidden' })
    await page.getByTitle('编辑', { exact: true }).last().click()
    assert.equal(await page.getByLabel('Access Key ID', { exact: true }).inputValue(), 'fixture-ak')
    await page.getByRole('button', { name: '取消', exact: true }).click()
    await page.getByTitle('编辑', { exact: true }).first().click()
    await protocol.selectOption('anthropic')
    await page.locator('#model-option-max_tokens').fill('8192')
    await page.getByRole('button', { name: '测试流式对话', exact: true }).click()
    const claudeProbe = await next(probes)
    assert.equal(claudeProbe.request().postDataJSON().api_options.max_tokens, 8192)
    await claudeProbe.fulfill({ json: { code: 200, data: { success: true, model_class: 'base', protocol: 'anthropic', stream: true, latency_ms: 10 } } })
    await page.getByTestId('model-test-result').filter({ hasText: 'Anthropic Claude' }).waitFor()
    await page.locator('#model-option-max_tokens').fill('4096')
    assert.ok(!(await page.getByTestId('model-test-result').innerText()).includes('测试通过'))
    if (process.env.MODEL_TEST_ARTIFACTS) await page.screenshot({ path: path.join(process.env.MODEL_TEST_ARTIFACTS, 'model-native-ui.png'), fullPage: true })
    assert.deepEqual(errors, [])
    console.log('PASS: legacy/base URLs, role filters, unknown/manual models, protocol and dimensions persistence, probe success/failure, stream probe, stale catalog/probe responses')
  } finally {
    await browser.close()
  }
})().catch(error => { console.error(error); process.exitCode = 1 })
