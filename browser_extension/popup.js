const status = document.getElementById('status');
document.getElementById('connect').onclick = async () => {
  const token = document.getElementById('token').value.trim();
  if (!token) { status.textContent = 'Paste the pairing code first.'; return; }
  await chrome.storage.local.set({clickyToken: token});
  const result = await chrome.runtime.sendMessage({connect: true});
  status.textContent = result.connected ? 'Connected to Clicky.' : 'Connecting… Keep Clicky open.';
};
document.getElementById('disconnect').onclick = async () => {
  await chrome.runtime.sendMessage({disconnect: true});
  status.textContent = 'Disconnected.';
};
chrome.runtime.sendMessage({status: true}).then(result => { status.textContent = result.connected ? 'Connected to Clicky.' : 'Not connected.'; });
