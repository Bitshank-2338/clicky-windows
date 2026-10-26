"""User-configured HTTP MCP connections with protected bearer tokens."""
import json
import asyncio
import uuid
from urllib.parse import urlparse

import httpx

from storage import setting, set_setting, credentials, set_credential


def save_connector(name, url, token=''):
    parsed = urlparse(url)
    if not name.strip() or len(name)>100 or parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError('Enter a name and an http/https MCP URL without embedded credentials')
    if parsed.scheme == 'http' and parsed.hostname not in {'127.0.0.1','localhost','::1'}:
        raise ValueError('Remote connectors require HTTPS')
    ident = uuid.uuid4().hex
    set_credential('connector_'+ident,token.strip())
    rows = setting('connectors',[])
    rows.append({'id':ident,'name':name.strip(),'url':url.strip()})
    set_setting('connectors',rows)
    return ident


def remove_connector(ident):
    set_setting('connectors',[row for row in setting('connectors',[]) if row['id'] != ident])
    set_credential('connector_'+ident,'')


def _decode_response(response):
    response.raise_for_status()
    if response.status_code == 202 or not response.content:
        return None
    if 'text/event-stream' in response.headers.get('content-type',''):
        for event in response.text.split('\n\n'):
            payload = '\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith('data:'))
            if payload:
                value = json.loads(payload)
                if isinstance(value,dict) and ('result' in value or 'error' in value):
                    return value
        raise ValueError('The connector returned no JSON-RPC response')
    return response.json()


class MCPConnection:
    def __init__(self,config):
        self.config = config
        self._session = None
        self._number = 0
        self.tools = []

    async def request(self,method,params=None,notification=False):
        self._number += 1
        request_id = self._number
        payload = {'jsonrpc':'2.0','method':method}
        if not notification:
            payload['id'] = request_id
        if params is not None:
            payload['params'] = params
        token = credentials().get('connector_'+self.config['id'],'')
        headers = {'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-06-18'}
        if token:
            headers['Authorization'] = 'Bearer '+token
        if self._session:
            headers['Mcp-Session-Id'] = self._session
        async with asyncio.timeout(30), httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
            async with client.stream('POST',self.config['url'],headers=headers,json=payload) as response:
                response.raise_for_status()
                body = bytearray()
                value = None
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body)>1_000_000:
                        raise ValueError('Connector response exceeded 1 MB')
                    if 'text/event-stream' in response.headers.get('content-type',''):
                        normalized = bytes(body).replace(b'\r\n',b'\n')
                        events = normalized.split(b'\n\n')[:-1]
                        for event in events:
                            data = b'\n'.join(line[5:].lstrip() for line in event.splitlines() if line.startswith(b'data:'))
                            if data:
                                candidate = json.loads(data)
                                if isinstance(candidate,dict) and candidate.get('id') == request_id:
                                    value = candidate
                                    break
                        if value is not None:
                            break
                self._session = response.headers.get('Mcp-Session-Id',self._session)
                if value is None:
                    value = _decode_response(httpx.Response(response.status_code,headers=response.headers,content=bytes(body),request=response.request))
        if value is None and notification:
            return None
        if not isinstance(value,dict) or (not notification and value.get('id') != request_id):
            raise ValueError('Connector response did not match this request')
        if 'error' in value:
            raise RuntimeError(str(value['error'].get('message','Connector rejected the request')))
        return value.get('result')

    async def connect(self):
        result = await self.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'Clicky Windows','version':'1.6.0'}})
        if not isinstance(result,dict) or result.get('protocolVersion') != '2025-06-18':
            raise ValueError('Connector does not support MCP 2025-06-18 Streamable HTTP')
        await self.request('notifications/initialized',notification=True)
        result = await self.request('tools/list')
        self.tools = result.get('tools',[])
        if not isinstance(self.tools,list) or len(self.tools)>500:
            raise ValueError('Connector tool catalog is invalid or too large')
        return self.tools

    async def call(self,name,arguments):
        if not self.tools:
            await self.connect()
        if name not in {tool['name'] for tool in self.tools} or not isinstance(arguments,dict):
            raise ValueError('Choose a tool from this connector and JSON object arguments')
        return await self.request('tools/call',{'name':name,'arguments':arguments})
