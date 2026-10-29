const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const NEWS = '11111111-1111-1111-1111-111111111111';
const REPORT = '22222222-2222-2222-2222-222222222222';
const items = [{id:NEWS,headline_fa:'خبر قدیمی ایران',published_at:'2020-01-01',category:'politics',topics:[{slug:'politics',name_fa:'سیاست'}]}, {id:REPORT,headline_fa:'گزارش تألیفی'}];
const elements = new Map();
const el = id => { if(!elements.has(id)) elements.set(id,{value:'',innerHTML:'',textContent:'',hidden:false}); return elements.get(id); };
const ctx = {console, AbortController,setTimeout,clearTimeout,encodeURIComponent,
  document:{getElementById:el},location:{replace:url=>ctx.destination=url},
  getJSON:async key=>({'data/news-archive.json':items,'data/pendar-reports.json':{[REPORT]:'https://pendar.io/story/'+REPORT+'/'},'data/story-permalinks.json':{slug_to_id:{legacy:NEWS}}}[key]||{}),
  show:()=>{},setTab:()=>{},setHash:()=>{},faN:String,esc:String,
  feedCard:row=>'<article>'+row.headline_fa+'</article>',groupedFeed:rows=>rows.map(row=>row.headline_fa).join('|'),
  showTopics:()=>{},openStory:id=>ctx.opened=id,
  fetch:async()=>({ok:true,json:async()=>({id:NEWS,headline_fa:'خبر تازه'})})};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root,'news-navigation.js'),'utf8'),ctx);
(async()=>{
  assert.equal((await ctx.loadNewsArchive()).length,1,'authored reports stay out of the news archive');
  assert.equal(await ctx.resolveNewsId('legacy'),NEWS);
  assert.equal(await ctx.pendarReportURL(REPORT),'https://pendar.io/story/'+REPORT+'/');
  await ctx.showNewsArchive('ایران');
  assert(el('news-archive-feed').innerHTML.includes('خبر قدیمی'));
  assert(!el('news-archive-feed').innerHTML.includes('تألیفی'));
  const snapshot={};
  await ctx.loadMissingNewsStory('story/'+NEWS+'.json',snapshot,1000);
  assert.equal(snapshot['story/'+NEWS+'.json'].id,NEWS);
  await assert.rejects(ctx.loadMissingNewsStory('story/../../other.json',{},1000));
  ctx.fetch=async()=>({ok:true,json:async()=>({id:REPORT})});
  await assert.rejects(ctx.loadMissingNewsStory('story/'+NEWS+'.json',{},1000),/identity mismatch/);
  ctx.fetch=async()=>({ok:false,status:404});
  await assert.rejects(ctx.loadMissingNewsStory('story/'+NEWS+'.json',{},1000),/HTTP 404/);
  assert.equal(ctx.destination,undefined,'failed news loads never redirect into Pendar');
  await ctx.openNewsEvent('event-'+NEWS);assert.equal(ctx.opened,NEWS);
  await ctx.openNewsEvent('editorial-example');assert.equal(ctx.destination,'https://pendar.io/event/editorial-example/');
  const app=fs.readFileSync(path.join(root,'app.js'),'utf8');
  vm.runInContext(app.match(/^async function openTopic\(slug\) \{[\s\S]*?^\}/m)[0],ctx);
  await ctx.openTopic('politics');
  assert(el('ta-feed').innerHTML.includes('خبر قدیمی'),'topic archives include older imported stories');
  console.log('PASS: archive search, authored reports, legacy IDs, fresh-news fallback and failed-load loop protection');
})().catch(error=>{console.error(error);process.exitCode=1;});
