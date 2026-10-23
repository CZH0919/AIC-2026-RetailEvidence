const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
(async () => {
const {changePercent, changeLabel} = await import(pathToFileURL(process.argv[2]));
assert.equal(changePercent((4 - 1030) / 1030), '99.6');
assert.equal(changePercent(-.999999), '>99.9');
assert.equal(changePercent(-1), '100');
assert.equal(changePercent(-.00001), '<0.1');
assert.equal(changeLabel({change: -1, comparison: {kind:'week',status:'available',current_quantity:0,previous_quantity:204}}), '月底7天售出0，前7天 204');
assert.equal(changeLabel({change:null,comparison:{kind:'week',status:'missing_records'}}), '记录不完整，暂不比较');
console.log('Signal display: six scenarios passed');
})().catch(error => { console.error(error); process.exit(1) });
