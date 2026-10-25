import assert from 'node:assert/strict'
import {calendarDay, calendarDates, validMonth, monthLastDay, dateRangeError, coverageError} from '../frontend/src/calendarDate.ts'
const checks = []
function test(name, run) { run(); checks.push({name, status:'PASS'}) }
for (const day of ['2026-04-01','2026-04-30','2024-02-29','2026-12-31','2027-01-01','0099-02-28']) test('valid '+day,()=>assert.notEqual(calendarDay(day),null))
for (const day of ['2026-02-29','2026-04-31','2026-13-01','0000-01-01','2026-4-1','2026-04-01T00:00:00Z']) test('invalid '+day,()=>assert.equal(calendarDay(day),null))
test('month boundary',()=>{assert.equal(monthLastDay('2024-02'),'2024-02-29');assert.equal(monthLastDay('2026-02'),'2026-02-28');assert.equal(monthLastDay('0099-02'),'0099-02-28');assert.equal(validMonth('2026-13'),false)})
test('Chinese separators and deduplication',()=>assert.deepEqual(calendarDates('2026-04-02，2026-04-03;2026-04-02\n2026-04-04；'),['2026-04-02','2026-04-03','2026-04-04']))
const base={month:'2026-04',complete:true,start:'2026-04-01',end:'2026-04-30',missing:'',closed:''}
test('valid coverage',()=>assert.equal(coverageError(base),null))
for (const [name,patch] of Object.entries({reverse:{start:'2026-05-01'},empty:{end:''},impossible:{end:'2026-04-31'},disjoint:{month:'2026-09'},oversize:{start:'2020-01-01'},conflict:{missing:'2026-04-02',closed:'2026-04-02'},invalidList:{missing:'2026-04-31'}})) test(name,()=>assert.equal(typeof coverageError({...base,...patch}),'string'))
test('unconfirmed coverage ignores inactive values',()=>assert.equal(coverageError({...base,complete:false,start:'bad'}),null))
test('partial month allowed',()=>assert.equal(coverageError({...base,start:'2026-04-15'}),null))
test('quality optional one sided range',()=>assert.equal(dateRangeError('2026-04-01',''),null))
test('quality reversed range',()=>assert.ok(dateRangeError('2026-04-30','2026-04-01')))
console.log(JSON.stringify({status:'PASS',checks},null,2))
