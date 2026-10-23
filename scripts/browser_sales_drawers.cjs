/** Real-browser regression for sales drawers. Uses an existing synthetic report. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE);
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const root=process.env.RETAIL_TEST_ROOT;
const base=process.env.RETAIL_BASE_URL||'http://127.0.0.1:18096';
const project=process.env.RETAIL_PROJECT_ID||'8bf9d58c-9ac4-48aa-9f42-6644d4f5a64a';
const run=process.env.RETAIL_RUN_ID||'35cf3631-064c-4a90-a845-b06485eb9a3e';
const results=[];let c,p;
const drawer=title=>p.locator('.ant-drawer-open').filter({has:p.locator('.ant-drawer-title').filter({hasText:new RegExp('^'+title+'$')})});
async function top(title){
 const d=drawer(title);await d.waitFor();await p.waitForTimeout(400);
 const probe=await d.locator('.ant-drawer-title').evaluate(el=>{
  const r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
  return {onTop:!!hit&&el.closest('.ant-drawer').contains(hit),focused:el.closest('.ant-drawer').contains(document.activeElement),width:document.documentElement.scrollWidth,viewport:innerWidth};
 });
 assert(probe.onTop,`${title}: obscured by another panel`);
 assert(probe.focused,`${title}: keyboard focus is behind panel`);
 assert(probe.width<=probe.viewport+1,`${title}: horizontal overflow`);
 return probe;
}
async function close(title){await drawer(title).locator('.ant-drawer-close').click();await p.waitForTimeout(400);}
(async()=>{
 c=await chromium.launchPersistentContext(path.join(root,'profile-after-'+new URL(base).port),{headless:true,viewport:{width:1440,height:1000}});
 p=await c.newPage();c.setDefaultTimeout(20000);
 const errors=[];p.on('pageerror',e=>errors.push(e.message));
 try{
  for(const width of [1440,390])for(const prewarm of [false,true]){
   await p.setViewportSize({width,height:1000});
   await p.goto(`${base}/projects/${project}?run=${run}`,{waitUntil:'networkidle'});
   if(prewarm){
    await p.getByRole('button',{name:/^.*查看依据$/}).click();await top('这份月报的依据');await close('这份月报的依据');
    await p.getByRole('button',{name:/问问销售助手/}).click();await top('销售助手');await close('销售助手');
   }
   await p.getByRole('button',{name:'查看商品和依据',exact:true}).first().click();
   const productTitle=await p.locator('.ant-drawer-open .ant-drawer-title').innerText();
   await top(productTitle);
   await p.getByRole('spinbutton',{name:'可售库存',exact:true}).fill('11');
   const draft='抽屉关闭后保留的未保存草稿';
   await p.getByRole('textbox',{name:'商品核对备注',exact:true}).fill(draft);
   await p.getByRole('button',{name:/查看计算依据/}).click();
   const probe=await top('这份月报的依据');
   await p.screenshot({path:path.join(root,`evidence/after_${width}_${prewarm?'warm':'fresh'}.png`)});
   // Help must sit above evidence; Escape closes only help, then only evidence.
   await drawer('这份月报的依据').locator('[data-help-id="UX32"]').click();
   const help=p.locator('[data-help-content="UX32"]');await help.waitFor();await p.waitForTimeout(500);
   const visible=await help.evaluate(el=>{const r=el.querySelector('h3').getBoundingClientRect();return el.contains(document.elementFromPoint(r.x+r.width/2,r.y+r.height/2));});
   assert(visible,'Help hidden behind evidence');
   await p.keyboard.press('Escape');await help.waitFor({state:'hidden'});await top('这份月报的依据');
   await p.keyboard.press('Escape');await p.waitForTimeout(500);
   assert.equal(await drawer('这份月报的依据').count(),0,'Escape did not close evidence');
   await top(productTitle);
   assert.equal(await p.getByRole('spinbutton',{name:'可售库存',exact:true}).inputValue(),'11');
   assert.equal(await p.getByRole('textbox',{name:'商品核对备注',exact:true}).inputValue(),draft);
   // Reopen and use the visible close button, not only keyboard.
   await p.getByRole('button',{name:/查看计算依据/}).click();await top('这份月报的依据');await close('这份月报的依据');await top(productTitle);
   await p.getByRole('button',{name:/问问这件商品/}).click();await top('销售助手');
   await p.getByRole('textbox',{name:'向销售助手提问',exact:true}).fill('这件商品的销量参考怎么理解？');
   if(prewarm&&width===1440){
    await drawer('销售助手').getByRole('button',{name:/^.*提问$/}).click();
    await p.locator('.sales-ai-answer').waitFor({timeout:120000});
    const text=await p.locator('.sales-ai-answer').innerText();assert(text.length>20);
    await p.getByRole('button',{name:'核对本次月报依据',exact:true}).click();await top('这份月报的依据');
    await close('这份月报的依据');await top('销售助手');
    assert.equal(await p.getByRole('textbox',{name:'向销售助手提问',exact:true}).inputValue(),'这件商品的销量参考怎么理解？');
   }
   await p.keyboard.press('Escape');await p.waitForTimeout(500);await top(productTitle);
   assert.equal(await p.getByRole('textbox',{name:'商品核对备注',exact:true}).inputValue(),draft);
   await close(productTitle);
   results.push({width,prewarm,status:'PASS',probe,productTitle});console.log('CASE_PASS',width,prewarm);
  }
  // Export remains usable after the overlay changes.
  await p.setViewportSize({width:1440,height:1000});
  await p.getByRole('button',{name:/导出月报/}).click();await top('导出月报');
  const wait=p.waitForEvent('download');await drawer('导出月报').getByRole('button',{name:/下载月报/}).click();const download=await wait;
  const file=path.join(root,'evidence/export_after.html');await download.saveAs(file);
  assert(fs.readFileSync(file,'utf8').includes('66,434.4'));
  await close('导出月报');
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(root,'evidence/after_'+new URL(base).port+'.json'),JSON.stringify({status:'PASS',base,project,run,cases:results,export:true,pageErrors:errors,date:new Date().toISOString()},null,2));
 }finally{await c.close();}
})().catch(async e=>{console.error(e);fs.writeFileSync(path.join(root,'evidence/after_failure.json'),JSON.stringify({error:String(e),cases:results},null,2));if(c)await c.close();process.exitCode=1});
