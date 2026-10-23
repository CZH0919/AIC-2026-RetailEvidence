const test=require('node:test'),assert=require('node:assert/strict');
const {splitReportNotices}=require('../../frontend/src/reportGuidance.ts');
const known=['只统计确认的正向销售，取消和退货不自动扣入净收入。','未提供库存和成本，销量变化不代表缺货、积压或利润变化。'];
test('only the two known background explanations move to help',()=>{const data=[known[0],'有待确认金额，请核对分类。',known[1],'新增限制：不能发布预测。'];assert.deepEqual(splitReportNotices(data),{explanations:known,warnings:[data[1],data[3]]});assert.equal(data.length,4);});
test('unknown or changed wording fails visibly rather than being silently hidden',()=>{const data=[known[0]+' 本月存在退货。','未提供库存和成本：数据有缺失。','库存日期未确认',''];assert.deepEqual(splitReportNotices(data),{explanations:[],warnings:data});});
test('empty notices, original order and repeat warnings are preserved',()=>{assert.deepEqual(splitReportNotices([]),{explanations:[],warnings:[]});assert.deepEqual(splitReportNotices(['待确认','待确认',known[1]]),{explanations:[known[1]],warnings:['待确认','待确认']});});
