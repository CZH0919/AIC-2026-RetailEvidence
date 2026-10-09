const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const net = require('node:net');
const { spawn } = require('node:child_process');
let browser, page, tunnel;
const evidenceDirectory = path.resolve(process.env.SALES_EVIDENCE_DIR || 'evidence_v2');

async function portOpen() {
  return new Promise(resolve => {
    const socket = net.connect(18080,'127.0.0.1');
    socket.on('connect',()=>{socket.destroy();resolve(true)});
    socket.on('error',()=>resolve(false));
  });
}

(async () => {
  const base = 'http://127.0.0.1:18080';
  const project = 'e1711757-601a-4e9a-a05f-037d7e6909e6';
  const directory = evidenceDirectory;
  fs.mkdirSync(directory, { recursive: true });
  if (!await portOpen()) {
    tunnel = spawn(process.env.SSH_BINARY || 'ssh', ['-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=30','-N','-L','18080:127.0.0.1:8000','aic-server'], {windowsHide:true});
    tunnel.stderr.on('data', data=>console.error(data.toString().trim()));
    for (let i=0;i<20 && !await portOpen();i++) await new Promise(resolve=>setTimeout(resolve,1000));
    assert(await portOpen(),'SSH tunnel unavailable');
  }
  browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || (process.platform === 'win32' ? 'C:/Program Files/Google/Chrome/Application/chrome.exe' : undefined), headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const api = context.request;
  context.setDefaultTimeout(90000);
  const listing = await (await api.get(`${base}/api/projects/${project}/runs?kind=sales&limit=100`)).json();
  const targetRun = process.env.SALES_RUN_ID || '81278059-612c-498b-9dd4-be6377e449de';
  let run = listing.items.find(r => r.id === targetRun);
  assert(run, 'No real monthly run');
  for (let i = 0; i < 120; i++) {
    run = await (await api.get(`${base}/api/projects/${project}/runs/${run.id}`, { timeout:120000 })).json();
    if (run.result) break;
    assert(!['failed','cancelled','resource_limited','interrupted'].includes(run.status), run.message);
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
  assert(run.result, 'Monthly report timed out');
  const report = run.result;
  console.log('Real monthly report loaded');
  page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${base}/projects/${project}?run=${run.id}`, { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: /本月卖得怎么样/ }).waitFor();
  assert.equal(await page.locator('.sales-scroll .ant-table-tbody > tr:not(.ant-table-measure-row)').count(), report.highlights.length);
  assert.equal(await page.locator('.sales-action').count(), report.actions.length);
  const canvasPixels = async () => page.locator('canvas').first().evaluate(c => {
    const pixels = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
    let colored = 0;
    for (let i=0; i<pixels.length; i+=4) if (pixels[i+3] && pixels[i+1]>pixels[i]+20 && pixels[i+1]>pixels[i+2]) colored++;
    return { width:c.width, height:c.height, colored };
  });
  const desktopCanvas = await canvasPixels();
  assert(desktopCanvas.colored > 100, 'Sales chart blank');
  if (report.previous_chart?.length) {
    await page.getByText('上月', {exact:true}).click();
    assert((await canvasPixels()).colored > 100, 'Previous month chart blank');
    await page.getByText('本月', {exact:true}).click();
  }
  await page.screenshot({ path:path.join(directory,'desktop_monthly.png'), fullPage:true });
  await page.getByRole('button', { name:/查看全部 .* 件/ }).click();
  await page.getByRole('heading', { name:'商品明细', exact:true }).waitFor();
  assert(page.url().includes('attention=1'));
  await page.locator('.ant-table-tbody .sales-item-name').first().click();
  await page.locator('.ant-drawer').getByRole('heading', { name:'接下来七天' }).waitFor();
  await page.waitForTimeout(450);
  await page.screenshot({ path:path.join(directory,'desktop_product.png') });
  await page.locator('.ant-drawer-close:visible').click();
  const anomalyItem = report.products.find(p => p.anomalies.length);
  assert(anomalyItem, 'Real dataset should include anomaly probes');
  await page.getByPlaceholder('商品名称或编号').fill(anomalyItem.id);
  await page.locator('.ant-table-tbody .sales-item-name').filter({hasText:anomalyItem.name}).first().click();
  await page.getByRole('button', {name:anomalyItem.anomalies[0].date,exact:true}).click();
  await page.locator('.sales-source-records').waitFor();
  const sourceRecords = await (await api.get(`${base}/api/projects/${project}/sales/runs/${run.id}/item-records?${new URLSearchParams({item_id:anomalyItem.id,day:anomalyItem.anomalies[0].date})}`, {timeout:120000})).json();
  assert(sourceRecords.count>0 && sourceRecords.items.length>0, 'Missing raw evidence');
  await page.waitForTimeout(450);
  await page.screenshot({path:path.join(directory,'desktop_source_records.png')});
  await page.locator('.sales-product-note .ant-select').first().click();
  await page.locator('.ant-select-dropdown:visible .ant-select-item-option-content').filter({hasText:sourceRecords.date}).click();
  await page.getByRole('button',{name:/保存核对记录$/}).waitFor();
  await page.getByPlaceholder('写下你查到的情况').fill('公开数据核对记录：尚未向商户确认原因。');
  const noteResponse = page.waitForResponse(response => response.url().endsWith('/item-notes') && response.request().method()==='PUT');
  await page.getByRole('button',{name:/保存核对记录$/}).click();
  const noteResult = await (await noteResponse).json();
  assert.equal(noteResult.value.reason,'unknown');
  assert.equal(noteResult.value.source,'user_note');
  assert.equal(noteResult.value.day,sourceRecords.date);
  const staleNote = await api.put(`${base}/api/projects/${project}/sales/runs/${run.id}/item-notes`,{data:{item_id:anomalyItem.id,day:sourceRecords.date,reason:'unknown',note:noteResult.value.note,expected_revision:noteResult.revision-1}});
  assert.equal(staleNote.status(),409,'Stale item note revision accepted');
  console.log('Item note saved; stale revision rejected');
  await page.locator('.ant-drawer-close:visible').click();
  const forecastItem = report.products.find(p => p.forecast);
  assert(forecastItem, 'Real eligible forecast missing');
  await page.getByText(`全部商品 ${report.products.length}`, {exact:true}).click();
  await page.getByPlaceholder('商品名称或编号').fill(forecastItem.id);
  await page.locator('.ant-table-tbody .sales-item-name').filter({hasText:forecastItem.name}).first().click();
  assert(await page.getByRole('button', {name:'计算数量参考',exact:true}).isDisabled(), 'Unknown inventory should block quantity calculation');
  assert.equal(await page.getByRole('spinbutton',{name:'可售库存',exact:true}).inputValue(), '');
  await page.locator('.ant-drawer-close:visible').click();
  await page.goto(`${base}/projects/${project}?run=${run.id}`, { waitUntil:'networkidle' });
  await page.getByRole('button',{name:/问问销售助手$/}).click();
  await page.getByPlaceholder('为什么建议我留意这件商品？').fill('请解释本月销量，并告诉我下次进货前先看什么。');
  const aiResponse = page.waitForResponse(response => response.url().endsWith('/ask') && response.request().method()==='POST');
  await page.getByRole('button',{name:/提问$/}).click();
  const aiResult = await (await aiResponse).json();
  assert.equal(aiResult.run_id,run.id);
  await page.locator('.sales-ai-answer').waitFor();
  await page.screenshot({path:path.join(directory,'desktop_ai.png')});
  console.log(`AI panel answered; ai_used=${aiResult.ai_used}`);
  await page.locator('.ant-drawer-close:visible').click();
  await page.getByRole('button', { name:/导出月报$/ }).click();
  await page.getByRole('checkbox', { name:'附上全部待关注商品' }).check();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('button', { name:/下载月报$/ }).click();
  await (await downloaded).saveAs(path.join(directory,'monthly_all_attention.html'));
  await page.locator('.ant-drawer-close:visible').click();
  await page.getByRole('button', { name:'生成月报', exact:true }).click();
  await page.locator('.sales-settings').waitFor();
  await page.screenshot({ path:path.join(directory,'desktop_confirmation.png'), fullPage:true });
  await page.locator('.ant-drawer-close:visible').click();
  await page.setViewportSize({ width:390,height:844 });
  await page.goto(`${base}/projects/${project}?run=${run.id}`, { waitUntil:'networkidle' });
  await page.getByRole('heading', { name:/本月卖得怎么样/ }).waitFor();
  const dimensions = await page.evaluate(() => ({ width:innerWidth, body:document.body.scrollWidth }));
  assert(dimensions.body <= dimensions.width + 1, JSON.stringify(dimensions));
  const mobileCanvas = await canvasPixels();
  assert(mobileCanvas.colored>100, 'Mobile chart blank');
  await page.screenshot({ path:path.join(directory,'mobile_monthly.png'), fullPage:true });
  await page.getByRole('button', { name:/查看全部 .* 件/ }).click();
  await page.locator('.sales-filter').waitFor();
  await page.screenshot({ path:path.join(directory,'mobile_products.png'), fullPage:true });
  const exportPage = await context.newPage();
  const exported = await api.get(`${base}/api/projects/${project}/sales/runs/${run.id}/report`);
  await exportPage.setContent(await exported.text());
  await exportPage.pdf({ path:path.join(directory,'monthly_summary.pdf'), format:'A4', printBackground:true });
  const result = { project,run_id:run.id,month:report.month,actual_products:report.products.length,
    attention_total:report.attention_ids.length,highlights:report.highlights.length,
    actions:report.actions.length,desktopCanvas,mobileCanvas,mobileDimensions:dimensions,
    source_records:{item_id:anomalyItem.id,date:sourceRecords.date,count:sourceRecords.count,shown:sourceRecords.shown},
    item_note_revision:noteResult.revision,item_note_conflict_checked:true,ai_used:aiResult.ai_used,unknown_inventory_blocked:true,errors };
  assert.equal(errors.length,0,errors.join('\n'));
  fs.writeFileSync(path.join(directory,'browser_acceptance.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result));
  await browser.close();
  if (tunnel) tunnel.kill();
})().catch(async error => {
  console.error(error);
  if (page) { await page.screenshot({ path:path.join(evidenceDirectory,'browser_failure.png'),fullPage:true }).catch(()=>{}); console.error((await page.locator('body').innerText()).slice(0,1500)); }
  if (browser) await browser.close();
  if (tunnel) tunnel.kill();
  process.exitCode = 1;
});
