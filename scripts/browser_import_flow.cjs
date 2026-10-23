const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base=process.env.SALES_BASE,root=process.env.RETAIL_TEST_ROOT,out=process.env.SALES_EVIDENCE_DIR;
assert(base && /^http:\/\/127\.0\.0\.1:\d+$/.test(base));assert(root && out);
let context,page;
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 context=await chromium.launchPersistentContext(process.env.SALES_BROWSER_PROFILE,{headless:true,acceptDownloads:true,downloadsPath:path.join(out,'downloads'),viewport:{width:1440,height:1000}});
 context.setDefaultTimeout(90000);const api=context.request,errors=[];
 const project=await(await api.post(base+'/api/projects',{data:{name:'浏览器完整演示 '+Date.now(),description:'公开原始数据派生；分类为验收声明，不是真实商户口径',color:'teal'}})).json();assert(project.id);
 page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')console.log('POST',r.url())});
 await page.goto(`${base}/projects/${project.id}`,{waitUntil:'networkidle'});
 await page.getByRole('button',{name:/上传新数据$/}).click();
 await page.getByLabel('选择本地数据文件',{exact:true}).setInputFiles(path.join(root,'evidence/browser_input/monthly_with_types.csv'));
 await page.getByRole('button',{name:'生成预览',exact:true}).click();
 await page.getByRole('heading',{name:'让每一列都有明确含义',exact:true}).waitFor();
 const fieldResponse=page.waitForResponse(r=>r.url().endsWith('/explain-fields')&&r.request().method()==='POST');await page.getByRole('button',{name:'请 AI 解释字段',exact:true}).click();const fieldAi=await(await fieldResponse).json();assert(fieldAi.ai_used,'Real CPU field explanation required');assert.equal(fieldAi.evidence_id,fieldAi.draft_id+':'+fieldAi.preview_token);await page.getByRole('button',{name:'使用列名建议（仍需确认）',exact:true}).click();assert(!(await page.getByRole('checkbox',{name:'我已核对字段对应、订单边界及上述业务含义',exact:true}).isChecked()));await page.screenshot({path:path.join(out,'01_field_cpu_ai.png'),fullPage:true});
 const select=async(name,option)=>{await page.getByRole('combobox',{name,exact:true}).click();await page.waitForTimeout(250);await page.locator('.ant-select-dropdown:visible').last().locator('.ant-select-item-option-content').filter({hasText:new RegExp('^'+option.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'$')}).click();await page.waitForTimeout(250);};
 for(const [field,column] of [['商品标识','item_id'],['商品名称','name'],['数量','quantity'],['行金额','amount'],['商品分类 / 业务记录类型','record_type']]) await select('对应'+field,column);
 await select('记录类型','某商品一个月的销售汇总');
 await page.getByLabel('月汇总月份',{exact:true}).fill('2011-10');
 await select('金额口径','使用行金额');await page.getByLabel('固定币种',{exact:true}).fill('GBP');await page.getByLabel('数量单位',{exact:true}).fill('原始商品单位');
 await select('取消与退货含义','确认全部为正向记录');
 await page.getByRole('checkbox',{name:'我已核对字段对应、订单边界及上述业务含义',exact:true}).check();
 await page.screenshot({path:path.join(out,'01_preview_mapping.png'),fullPage:true});
 const savedResponse=page.waitForResponse(r=>r.url().endsWith('/confirm')&&r.request().method()==='POST');await page.getByRole('button',{name:'确认并创建版本',exact:true}).click();const saved=await(await savedResponse).json();assert(saved.id);
 await page.locator('.classification-editor').waitFor();
 // Source type column is explicitly mapped. Only confirmed exact category rules apply.
 for(const [i,kind,label,treatment] of [[1,'physical_product','实物商品','计入销售额'],[2,'shipping_service','运费/服务','不计入销售额'],[3,'manual_adjustment','人工调整','不计入销售额'],[4,'other','其他','不计入销售额']]){
  await page.getByRole('button',{name:'添加分类规则',exact:true}).click();await select('匹配范围 '+i,'已映射类型/分类精确匹配');await page.getByLabel('匹配值 '+i,{exact:true}).fill(kind);await select('记录类型 '+i,label);await select('金额口径 '+i,treatment);await page.getByLabel('分类依据 '+i,{exact:true}).fill('公开数据派生验收声明，需真实商户另行确认');
 }
 await page.getByRole('checkbox',{name:'我已核对本数据版本的记录类型及金额口径，待确认项保留不猜测',exact:true}).check();
 await page.getByLabel('分析月份',{exact:true}).fill('2011-10');
 await page.screenshot({path:path.join(out,'02_classification.png'),fullPage:true});
 await page.getByRole('button',{name:/检查数据$/}).click();await page.getByRole('heading',{name:'数据检查结果',exact:true}).waitFor({timeout:180000});
 await page.screenshot({path:path.join(out,'03_quality.png'),fullPage:true});console.log('BUTTONS',await page.locator('.sales-drawer-footer button').evaluateAll(xs=>xs.map(x=>({text:x.textContent,disabled:x.disabled,html:x.outerHTML.slice(0,600)}))));
 console.log('Generate button enabled',await page.getByRole('button',{name:/确认并生成月报$/}).isEnabled());const [runResponse]=await Promise.all([page.waitForResponse(r=>r.url().endsWith('/sales/runs')&&r.request().method()==='POST',{timeout:30000}),page.getByRole('button',{name:/确认并生成月报$/}).click({timeout:30000})]);let run=await runResponse.json();
 for(let i=0;i<120;i++){run=await(await api.get(`${base}/api/projects/${project.id}/runs/${run.id}`)).json();if(run.result)break;assert(!['failed','resource_limited','cancelled'].includes(run.status),run.message);await page.waitForTimeout(1000)}
 assert.equal(new URL(page.url()).searchParams.get('run'),run.id,'New report must be reflected in the URL before refresh');
 assert(run.result);assert.equal(run.result.summary.quantity,626765);assert.equal(run.result.summary.amount,1105884.75);assert.equal(run.result.summary.products,2863);assert.equal(run.result.classification.pending_product_rows,0);
 await page.goto(`${base}/projects/${project.id}?run=${run.id}`,{waitUntil:'networkidle'});await page.getByRole('heading',{name:/本月卖得怎么样/}).waitFor();
 await page.getByText('核对全部业务记录（含待确认、运费与调整）',{exact:true}).click();await page.screenshot({path:path.join(out,'04_monthly_business_records.png'),fullPage:true});
 await page.getByRole('button',{name:/查看全部 .* 件/}).click();await page.getByRole('heading',{name:'商品明细',exact:true}).waitFor();
 await page.getByText('全部商品 '+run.result.summary.products,{exact:true}).click();await page.getByPlaceholder('商品名称或编号').fill('23084');await page.locator('.sales-item-name').first().click();await page.getByRole('heading',{name:'接下来七天',exact:true}).waitFor();assert.equal(run.result.forecast.status,'unavailable');
 await page.getByPlaceholder('写下你查到的情况').fill('公开数据验收，月汇总无逐日异常，未向商户确认经营原因。');
 await page.getByRole('button',{name:/保存核对记录$/}).click();await page.screenshot({path:path.join(out,'05_product_note.png')});await page.locator('.ant-drawer-close:visible').click();
 assert.equal(await page.getByPlaceholder('商品名称或编号').inputValue(),'23084');
 await page.goto(`${base}/projects/${project.id}?run=${run.id}`,{waitUntil:'networkidle'});await page.getByRole('button',{name:/问问销售助手$/}).click();await page.getByPlaceholder('为什么建议我留意这件商品？').fill('请解释本月销量，并告诉我下次进货前先看什么。');const aiResponse=page.waitForResponse(r=>r.url().endsWith('/ask')&&r.request().method()==='POST');await page.getByRole('button',{name:/提问$/}).click();const ai=await(await aiResponse).json();assert(ai.ai_used,'Real CPU inference did not succeed');assert.equal(ai.evidence_id,run.id+':'+run.result.classification.sha256);await page.screenshot({path:path.join(out,'06_real_cpu_ai.png')});await page.locator('.ant-drawer-close:visible').click();
 await page.getByRole('button',{name:/导出月报$/}).click();for(const [label,name] of [['下载月报','report.html'],['下载全部商品表','products.csv'],['下载分类金额分项','classification.csv'],['下载全部业务记录分类','business_records.csv'],['下载报告 JSON','report.json']]){const download=page.waitForEvent('download');await page.getByRole('button',{name:new RegExp(label+'$')}).click();await(await download).saveAs(path.join(out,name))}await page.locator('.ant-drawer-close:visible').click();
 const printPage=await context.newPage();await printPage.goto('file://'+path.join(out,'report.html'));await printPage.pdf({path:path.join(out,'report.pdf'),format:'A4',printBackground:true});await printPage.close();
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'07_mobile_monthly.png'),fullPage:true});assert(await page.evaluate(()=>document.body.scrollWidth<=innerWidth+1));
 const sessions=[];for(let i=0;i<3;i++)sessions.push(await context.browser().newContext({viewport:{width:1280,height:800}}));await Promise.all(sessions.map(async c=>{const p=await c.newPage();await p.goto(`${base}/projects/${project.id}?run=${run.id}`,{waitUntil:'networkidle'});await p.getByRole('heading',{name:/本月卖得怎么样/}).waitFor()}));for(const c of sessions)await c.close();
 assert.equal(errors.length,0);const result={status:'PASS',project_id:project.id,version_id:saved.id,run_id:run.id,source_sha256:saved.sha256,summary:run.result.summary,classification_sha256:run.result.classification.sha256,field_ai:fieldAi,ai,three_browser_sessions:true,errors};fs.writeFileSync(path.join(out,'browser_import_acceptance.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({status:result.status,project_id:result.project_id,version_id:result.version_id,run_id:result.run_id,summary:result.summary,ai_used:ai.ai_used,ai_mode:ai.mode,ai_answer:ai.answer,three_browser_sessions:true,errors}));await context.close();
})().catch(async e=>{console.error(e);if(page){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});console.error((await page.locator('body').innerText()).slice(-4500))}if(context)await context.close();process.exitCode=1});
