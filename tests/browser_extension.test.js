const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
let clicks=0;
const element={tagName:'BUTTON',type:'button',isConnected:true,disabled:false,innerText:'Save',getAttribute:()=>'',getBoundingClientRect:()=>({width:100,height:30,top:10,left:10,bottom:40,right:110}),click:()=>{clicks++;}};
const context={console,URL,crypto:{randomUUID:()=> 'test-epoch'},innerWidth:800,innerHeight:600,
  document:{title:'Owned test page',body:{innerText:'Test content'},querySelectorAll:()=>[element]},
  location:{href:'https://owned.example/'},
  chrome:{storage:{local:{get:async()=>({})}},runtime:{onMessage:{addListener:()=>{}}},alarms:{create:()=>{},onAlarm:{addListener:()=>{}}}},
  setInterval:()=>0,clearInterval:()=>{},scrollBy:()=>{},WebSocket:class{}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('browser_extension/background.js','utf8'),context);
const page=context.pageOperation;
const snapshot=page({operation:'snapshot'});
assert.equal(snapshot.elements[0].label,'Save');
assert.throws(()=>page({operation:'click',ref:0,epoch:'stale'}));
assert.equal(clicks,0);
assert.equal(page({operation:'click',ref:0,epoch:snapshot.epoch}).done,true);
assert.equal(clicks,1);
element.type='password';
assert.throws(()=>page({operation:'click',ref:0,epoch:snapshot.epoch}));
assert.equal(clicks,1);
console.log('Browser page handler: snapshot, stale-ref refusal, click, protected-field refusal passed.');
