let socket = null;
let heartbeat = null;

async function connect() {
  if (socket && socket.readyState <= 1) return;
  const {clickyToken} = await chrome.storage.local.get('clickyToken');
  if (!clickyToken) return;
  socket = new WebSocket('ws://127.0.0.1:43129/bridge');
  socket.onopen = () => {
    socket.send(JSON.stringify({token: clickyToken}));
    heartbeat = setInterval(() => { if (socket?.readyState === 1) socket.send(JSON.stringify({ping: true})); }, 20000);
  };
  socket.onclose = () => { clearInterval(heartbeat); socket = null; };
  socket.onerror = () => {};
  socket.onmessage = async ({data}) => {
    let request;
    try {
      request = JSON.parse(data);
      if (!request.id) return;
      const result = await perform(request);
      socket?.send(JSON.stringify({id: request.id, result}));
    } catch (error) {
      if (request?.id && socket?.readyState === 1) socket.send(JSON.stringify({id: request.id, error: String(error.message || error)}));
    }
  };
}

async function perform(request) {
  const allowed = ['snapshot', 'tabs', 'open', 'back', 'click', 'fill', 'press', 'scroll'];
  if (!allowed.includes(request.operation)) throw new Error('Unsupported browser operation');
  if (request.operation === 'tabs') return (await chrome.tabs.query({})).filter(t => /^https?:/.test(t.url || '')).map(t => ({id:t.id,title:t.title,url:t.url}));
  if (request.operation === 'open') {
    const url = new URL(request.url);
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error('Only http/https pages are supported');
    const tab = await chrome.tabs.create({url:url.href});
    return {id:tab.id,url:tab.url};
  }
  const tab = request.tabId ? await chrome.tabs.get(request.tabId) : (await chrome.tabs.query({active:true,lastFocusedWindow:true}))[0];
  if (!tab || !/^https?:/.test(tab.url || '')) throw new Error('Select an ordinary web page first');
  if (/password|bitwarden|1password|banking|sign\s*in|login/i.test(tab.title || '')) throw new Error('Clicky will not inspect or operate a sensitive page');
  if (request.operation === 'back') { await chrome.tabs.goBack(tab.id); return {done:true}; }
  const results = await chrome.scripting.executeScript({target:{tabId:tab.id},world:'ISOLATED',args:[request],func: pageOperation});
  return results[0]?.result;
}

function pageOperation(request) {
  function visible(element) { const r=element.getBoundingClientRect(); return r.width>0 && r.height>0 && r.bottom>0 && r.right>0 && r.top<innerHeight && r.left<innerWidth; }
  if (request.operation === 'snapshot') {
    const elements = [...document.querySelectorAll('button,a[href],input,textarea,select,[role="button"]')].filter(e => visible(e) && e.type !== 'password').slice(0,150);
    globalThis.__clickyRefs = elements;
    globalThis.__clickyEpoch = crypto.randomUUID();
    return {epoch:globalThis.__clickyEpoch,title:document.title,url:location.href,text:(document.body?.innerText || '').slice(0,16000),elements:elements.map((e,index) => ({ref:index,role:e.tagName.toLowerCase(),label:(e.getAttribute('aria-label') || e.innerText || e.placeholder || e.name || '').slice(0,160)}))};
  }
  if (request.operation === 'scroll') {
    if (!Number.isFinite(request.amount) || Math.abs(request.amount)>1000) throw new Error('Scroll is limited to 1000 pixels');
    scrollBy(0,request.amount); return {done:true};
  }
  if (request.epoch !== globalThis.__clickyEpoch || !Number.isInteger(request.ref)) throw new Error('Read this page again before using an element');
  const element = globalThis.__clickyRefs?.[request.ref];
  if (!element?.isConnected || !visible(element) || element.type === 'password' || element.disabled) throw new Error('That element changed or is protected');
  if (request.operation === 'click') { element.click(); return {done:true}; }
  if (request.operation === 'fill') {
    if (typeof request.text !== 'string' || request.text.length>2000 || /[\r\n]/.test(request.text)) throw new Error('Use at most 2000 characters on one line');
    if (!['INPUT','TEXTAREA'].includes(element.tagName)) throw new Error('Choose an editable field');
    const prototype = element.tagName === 'INPUT' ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype;
    Object.getOwnPropertyDescriptor(prototype,'value').set.call(element,request.text);
    element.dispatchEvent(new Event('input',{bubbles:true})); element.dispatchEvent(new Event('change',{bubbles:true})); return {done:true};
  }
  if (request.operation === 'press') {
    if (!['Enter','Tab','Escape'].includes(request.key)) throw new Error('Unsupported key');
    element.focus(); element.dispatchEvent(new KeyboardEvent('keydown',{key:request.key,bubbles:true})); element.dispatchEvent(new KeyboardEvent('keyup',{key:request.key,bubbles:true}));
    return {done:true,note:'Synthetic page key event sent; sites may ignore it. Use Clicky Drive for native keyboard input.'};
  }
  throw new Error('Unsupported page operation');
}

chrome.runtime.onMessage.addListener((message,_sender,reply) => {
  if (message.disconnect) {
    chrome.storage.local.remove('clickyToken'); socket?.close(); reply({connected:false}); return;
  }
  if (message.connect) connect();
  reply({connected:socket?.readyState===1});
});
chrome.alarms.create('clicky-reconnect',{periodInMinutes:1});
chrome.alarms.onAlarm.addListener(() => connect());
connect();
