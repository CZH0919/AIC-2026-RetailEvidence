const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),cp=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),baseline='160a90c47b6f2a675386355cc283fb869e85334a';
const read=(f,old)=>old?cp.execFileSync('git',['show',baseline+':'+f],{cwd:root,encoding:'utf8'}):fs.readFileSync(path.join(root,f),'utf8');
// Explicitly allow only the reviewed alignment, portal classes and visible rule labels.
// Compare the rest of both whole components, including all business code and handlers.
const disclosurePresentationPairs = [
["import { useNavigate, useSearchParams } from 'react-router-dom'", "import { Link, useNavigate, useSearchParams } from 'react-router-dom'"],
["<div className=\"sales-bottom\"><Button icon={<MessageOutlined />} onClick={() => setAi(true)}>问问销售助手</Button></div>", "<div className=\"sales-bottom\"><Button icon={<MessageOutlined />} onClick={() => setAi(true)}>问问销售助手</Button><Link to={`${root}/quality`}>更多分析</Link></div>"],
  [
    "import { HelpHint } from './HelpHint'\nimport { splitReportNotices } from '../reportGuidance'",
    "import { HelpHint } from './HelpHint'"
  ],
  [
    "  const invalidClassifications = classifications.some(policy => classificationProblems(policy).length > 0)\n  const { explanations: reportExplanations, warnings: reportWarnings } = splitReportNotices(report?.notices ?? [])",
    "  const invalidClassifications = classifications.some(policy => classificationProblems(policy).length > 0)"
  ],
  [
    "<details className=\"sales-band sales-financial-details\"><summary>分类与金额明细</summary><h3>分类口径与金额分项</h3>",
    "<section className=\"sales-band\"><h3>分类口径与金额分项</h3>"
  ],
  [
    "</details>}\n    {report && !productsMode && reportWarnings.map(n=><p className=\"sales-caveat sales-current-warning\" key={n}>{n}</p>)}",
    "{report.notices.map(n=><p className=\"sales-caveat\" key={n}>{n}</p>)}</section>}"
  ],
  [
    "<HelpHint topic=\"UX27\" context={reportExplanations.join(\" \")} />",
    "<HelpHint topic=\"UX27\" />"
  ],
  [
    "<details className=\"sales-focus-reasons sales-explanation\"><summary>查看关注原因</summary>{highlights.map(p => <p key={p.id}><strong>{p.name}</strong><span>{p.reason}</span></p>)}</details>",
    "<div className=\"sales-focus-reasons\">{highlights.map(p => <p key={p.id}><strong>{p.name}</strong><span>{p.reason}</span></p>)}</div>"
  ],
  [
    "<details className=\"sales-action-evidence sales-explanation\"><summary>建议依据</summary><p>{a.reason} · {a.review}</p></details>",
    "<small>{a.reason} · {a.review}</small>"
  ],
  [
    "<HelpHint topic=\"UX16\" context=\"销量、商品列表与备货只包含已确认实物。金额是否计入需另行确认；不清楚的记录请保留待确认。修改后须重新检查并生成新月报，旧报告保留。\" />\n    <p>不清楚的记录保留“待确认”。</p>",
    "<HelpHint topic=\"UX16\" />\n    <p>销量、商品列表与备货只包含已确认实物。金额是否计入需另行确认；不清楚的记录请保留待确认。修改后须重新检查并生成新月报，旧报告保留。</p>"
  ]
];
function normalize(t){for (const [changed, original] of disclosurePresentationPairs) t=t.replaceAll(changed,original); return t.replace(/, ?align: ?'right'( as const)?/g,'')
 .replace(/ className="(?:retail-settings-drawer|retail-product-drawer|classification-rule-remove|classification-rule-basis|classification-rule)"/g,'')
 .replace(/ style=\{\{border:'1px solid #ddd',padding:12,marginBottom:12\}\}/g,'')
 .replace(/ style=\{\{borderTop:'1px solid #ddd',marginTop:12,paddingTop:8\}\}/g,'')
 .replace(/<h5>规则 \{i\+1\}<\/h5>/g,'')
 .replace(/<span>(匹配范围|匹配值|记录类型|金额口径|分类依据)<\/span>/g,'')
 .replace(/<label>|<\/label>/g,'').replace(/\s+/g,' ').trim();}
for(const n of ['ClassificationEditor','SalesWorkspace'])test(n+' whole source respects presentation-only allowlist',()=>{const f='frontend/src/components/'+n+'.tsx';assert.equal(normalize(read(f,false)),normalize(read(f,true)));});
test('backend, dependency locks, route definitions, APIs, help, charts and overlay layers are untouched',()=>{const files=['backend','frontend/package.json','frontend/package-lock.json','frontend/src/App.tsx','frontend/src/api.ts','frontend/src/data.ts','frontend/src/retail.ts','frontend/src/quality.ts','frontend/src/components/HelpHint.tsx','frontend/src/helpContent.ts','frontend/src/overlayLayers.ts','frontend/src/components/SalesChart.tsx'];assert.equal(cp.execFileSync('git',['diff',baseline,'--',...files],{cwd:root,encoding:'utf8'}),'');});

// The only allowed project-shell change is making the existing analysis link unconditional.
test("project shell differs only by the always-visible analysis navigation link",()=>{const f="frontend/src/pages/RetailProjectSpace.tsx";const before="{path.endsWith('/quality') && <NavLink to={`/projects/${project.id}/quality`}>更多分析</NavLink>}";const after="<NavLink to={`/projects/${project.id}/quality`}>更多分析</NavLink>";const original=read(f,true);assert.equal(original.split(before).length,2);assert.equal(read(f,false),original.replace(before,after));});
