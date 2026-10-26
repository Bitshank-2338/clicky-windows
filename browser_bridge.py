"""Loopback-only browser connection for Clicky's original Chromium extension."""
import asyncio
import json
import secrets
import uuid

from aiohttp import web, WSMsgType
from storage import credentials, set_credential

PORT = 43129
OPERATIONS = {"snapshot", "tabs", "open", "back", "click", "fill", "press", "scroll"}


def pairing_token():
    token = credentials().get("browser_pairing")
    if not token:
        token = secrets.token_urlsafe(32)
        set_credential("browser_pairing", token)
    return token


class BrowserBridge:
    def __init__(self):
        self.socket = None
        self.pending = {}
        self.runner = None

    async def start(self, port=PORT):
        app = web.Application(client_max_size=1_000_000)
        app.router.add_get('/bridge',self.connect)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        try:
            site=web.TCPSite(self.runner,'127.0.0.1',port)
            await site.start()
            self.port=site._server.sockets[0].getsockname()[1]
        except Exception:
            await self.runner.cleanup()
            self.runner = None
            raise

    async def connect(self,request):
        origin = request.headers.get('Origin','')
        if not origin.startswith('chrome-extension://') or len(origin.split('://')[-1]) != 32:
            raise web.HTTPForbidden(text='Use the paired Clicky extension')
        socket = web.WebSocketResponse(max_msg_size=1_000_000,heartbeat=20)
        await socket.prepare(request)
        try:
            hello = await asyncio.wait_for(socket.receive_json(),timeout=5)
            if not isinstance(hello,dict) or not secrets.compare_digest(str(hello.get('token','')),pairing_token()):
                await socket.close(code=1008,message=b'Pairing token rejected')
                return socket
            if self.socket and not self.socket.closed:
                await socket.close(code=1008,message=b'Another browser is connected')
                return socket
            self.socket = socket
            await socket.send_json({'connected':True})
            async for message in socket:
                if message.type == WSMsgType.TEXT:
                    response = json.loads(message.data)
                    if not isinstance(response,dict):
                        continue
                    future = self.pending.get(response.get('id'))
                    if future and not future.done():
                        future.set_result(response)
        except (ValueError,asyncio.TimeoutError):
            await socket.close(code=1008)
        finally:
            if self.socket is socket:
                self.socket = None
                for future in self.pending.values():
                    if not future.done():
                        future.set_exception(ConnectionError('Clicky browser disconnected'))
        return socket

    async def command(self,operation,**arguments):
        if operation not in OPERATIONS:
            raise ValueError('Unknown browser operation')
        if not self.socket or self.socket.closed:
            raise ConnectionError('Connect the Clicky browser extension first')
        ident = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        try:
            await self.socket.send_json({'id':ident,'operation':operation,**arguments})
            response = await asyncio.wait_for(future,timeout=20)
            if response.get('error'):
                raise RuntimeError(response['error'])
            return response.get('result')
        finally:
            self.pending.pop(ident,None)

    async def close(self):
        if self.socket:
            await self.socket.close()
        if self.runner:
            await self.runner.cleanup()
