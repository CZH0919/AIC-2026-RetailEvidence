const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),cp=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),baseline='160a90c47b6f2a675386355cc283fb869e85334a';
const read=(f,old)=>old?cp.execFileSync('git',['show',baseline+':'+f],{cwd:root,encoding:'utf8'}):fs.readFileSync(path.join(root,f),'utf8');
// Explicitly allow only the reviewed alignment, portal classes and visible rule labels.
// Compare the rest of both whole components, including all business code and handlers.
function normalize(t){return t.replace(/, ?align: ?'right'( as const)?/g,'')
 .replace(/ className="(?:retail-settings-drawer|retail-product-drawer|classification-rule-remove|classification-rule-basis|classification-rule)"/g,'')
 .replace(/ style=\{\{border:'1px solid #ddd',padding:12,marginBottom:12\}\}/g,'')
 .replace(/ style=\{\{borderTop:'1px solid #ddd',marginTop:12,paddingTop:8\}\}/g,'')
 .replace(/<h5>规则 \{i\+1\}<\/h5>/g,'')
 .replace(/<span>(匹配范围|匹配值|记录类型|金额口径|分类依据)<\/span>/g,'')
 .replace(/<label>|<\/label>/g,'').replace(/\s+/g,' ').trim();}
for(const n of ['ClassificationEditor','SalesWorkspace'])test(n+' whole source respects presentation-only allowlist',()=>{const f='frontend/src/components/'+n+'.tsx';assert.equal(normalize(read(f,false)),normalize(read(f,true)));});
test('backend, dependency locks, routes, APIs, help, charts and overlay layers are untouched',()=>{const files=['backend','frontend/package.json','frontend/package-lock.json','frontend/src/App.tsx','frontend/src/pages/RetailProjectSpace.tsx','frontend/src/api.ts','frontend/src/data.ts','frontend/src/retail.ts','frontend/src/quality.ts','frontend/src/components/HelpHint.tsx','frontend/src/helpContent.ts','frontend/src/overlayLayers.ts','frontend/src/components/SalesChart.tsx'];assert.equal(cp.execFileSync('git',['diff',baseline,'--',...files],{cwd:root,encoding:'utf8'}),'');});
