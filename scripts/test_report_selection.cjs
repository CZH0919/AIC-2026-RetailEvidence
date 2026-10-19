const assert = require('node:assert/strict');
async function main() {
const {monthlyReports, reportQuery} = await import(require('node:url').pathToFileURL(process.argv[2]));
const row = (id, month, status='succeeded', finished='2026-10-19T12:00:00Z', has_result=true) => ({id, status, has_result, finished_at:finished, created_at:finished, parameters:{sales:{month}}});
const input=[row('old','2011-10','succeeded','2026-10-08'),row('new','2011-10'),row('failed','2011-10','failed','2026-10-20'),row('running','2011-11','running'),row('empty','2011-11','succeeded','2026-10-21',false),row('sept','2011-09'),row('badmonth','2011-99')];
const groups=monthlyReports(input);
assert.deepEqual(groups.map(g=>g.month),['2011-10','2011-09']);
assert.deepEqual(groups[0].reports.map(r=>r.id),['new','old']);
assert.equal(input[0].id,'old');
assert.equal(reportQuery('run=old&pairingSource=v&pairingRun=a&pairingItems=x&attention=1','new').toString(),'run=new&attention=1');
assert.deepEqual(monthlyReports([row('pending','2026-10','running')]),[]);
console.log('Report selection scenarios passed: duplicate months, latest successful, failed/running/empty exclusion, historical retention, query scope.');
}
main().catch(error => {console.error(error);process.exitCode=1});
