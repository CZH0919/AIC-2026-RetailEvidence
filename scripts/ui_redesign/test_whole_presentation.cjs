const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),cp=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'../..'),base='40ad43cdbb2d2b03b293761257661fcb0b497d38',pairs=require('./whole_presentation_allowlist.json');
// Apply only the reviewed literal display patch to the immutable approved source.
// Compare the whole component, including every handler, field, condition and payload.
for(const f of new Set(pairs.map(p=>p.file)))test(f+' preserves every non-display line',()=>{let expected=cp.execFileSync('git',['show',base+':'+f],{cwd:root,encoding:'utf8'});for(const p of pairs.filter(p=>p.file===f)){assert(expected.includes(p.original),p.original);expected=expected.replaceAll(p.original,p.changed);}const actual=fs.readFileSync(path.join(root,f),'utf8');assert.equal(actual.replaceAll('\r\n','\n'),expected.replaceAll('\r\n','\n'));});
