"""Opt-in peer sessions on a trusted LAN; shares answers/Sketch, never input control."""
import json
import secrets
from urllib.parse import urlparse, parse_qs
import aiohttp
from aiohttp import web, WSMsgType


def checked_message(value):
    if not isinstance(value,dict) or value.get('type') not in {'qa','scene'}:
        raise ValueError('Shared sessions accept answers and Sketch scenes only')
    if value['type']=='qa':
        if any(not isinstance(value.get(k),str) or len(value[k])>20000 for k in ('q','a')):
            raise ValueError('Shared answer exceeds its limit')
        return {'type':'qa','q':value['q'],'a':value['a']}
    from drawing import validate_scene
    return {'type':'scene','scene':validate_scene(value.get('scene'))}


class CollabSession:
    def __init__(self):
        self.code=None
        self.peers=set()
        self._on_message=None
        self._runner=None
        self._client=None
        self._socket=None
        self._reader=None
        self._key=secrets.token_urlsafe(24)

    def on_message(self,callback):
        self._on_message=callback

    async def start_host(self,host='127.0.0.1',port=0):
        if self._runner or self._client:
            raise ValueError('Stop the existing shared session first')
        app=web.Application(client_max_size=100000)
        app.router.add_get('/session',self._accept)
        self._runner=web.AppRunner(app)
        await self._runner.setup()
        try:
            site=web.TCPSite(self._runner,host,port);await site.start()
            actual_port=site._server.sockets[0].getsockname()[1]
            address='YOUR-LAN-IP' if host=='0.0.0.0' else host
            self.code=f'http://{address}:{actual_port}/session?key={self._key}'
            return self.code
        except Exception:
            await self.stop()
            raise

    async def _accept(self,request):
        if request.headers.get('Origin') or not secrets.compare_digest(request.query.get('key',''),self._key):
            raise web.HTTPForbidden()
        socket=web.WebSocketResponse(max_msg_size=100000,heartbeat=20)
        await socket.prepare(request)
        if len(self.peers)>=4:
            await socket.close(code=1008);return socket
        self.peers.add(socket)
        try:
            async for msg in socket:
                if msg.type==WSMsgType.TEXT:
                    value=checked_message(json.loads(msg.data))
                    if self._on_message:self._on_message(value)
                    for peer in tuple(self.peers):
                        if peer is not socket and not peer.closed:await peer.send_json(value)
        except (ValueError,ConnectionError):
            await socket.close(code=1008)
        finally:self.peers.discard(socket)
        return socket

    async def join(self,code):
        parsed=urlparse(code)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.path!='/session' or not parse_qs(parsed.query).get('key'):
            raise ValueError('Paste a full Clicky shared-session link')
        if self._runner or self._client:raise ValueError('Stop the existing session first')
        self._client=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None,sock_connect=10))
        try:
            self._socket=await self._client.ws_connect(code,max_msg_size=100000,heartbeat=20)
            self.code=code
            import asyncio
            self._reader=asyncio.create_task(self._receive())
            return True
        except Exception:
            await self.stop();raise

    async def _receive(self):
        async for message in self._socket:
            if message.type==WSMsgType.TEXT:
                value=checked_message(json.loads(message.data))
                if self._on_message:self._on_message(value)

    async def send(self,msg):
        value=checked_message(msg)
        if self._socket and not self._socket.closed:await self._socket.send_json(value)
        for peer in tuple(self.peers):
            if not peer.closed:await peer.send_json(value)

    async def stop(self):
        if self._reader:
            self._reader.cancel()
            import asyncio
            await asyncio.gather(self._reader,return_exceptions=True)
        if self._socket:await self._socket.close()
        for peer in tuple(self.peers):await peer.close()
        if self._client:await self._client.close()
        if self._runner:await self._runner.cleanup()
        self.code=None;self._runner=None;self._client=None;self._socket=None;self._reader=None
        self.peers.clear()
