import httpx
import asyncio
import aiohttp

from audio.stt.base_stt import BaseSTT
from audio.capture import pcm16_to_wav
from config import cfg

DEEPGRAM_URL = "https://api.deepgram.com/v1/listen"


class DeepgramSTT(BaseSTT):
    """
    Deepgram Nova-3, with live partials and a same-provider upload fallback.
    """

    def __init__(self):
        if not cfg.deepgram_api_key:
            raise ValueError('Add a Deepgram API key before selecting Deepgram speech recognition')

    async def transcribe(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        wav_bytes = pcm16_to_wav(pcm_bytes, sample_rate)
        headers = {
            "Authorization": f"Token {cfg.deepgram_api_key}",
            "Content-Type": "audio/wav",
        }
        params = {
            "model": "nova-3",
            "language": cfg.whisper_language or "multi",
            "smart_format": "true",
            "punctuate": "true",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                DEEPGRAM_URL,
                headers=headers,
                params=params,
                content=wav_bytes,
            )
            r.raise_for_status()
            data = r.json()
            transcript = (
                data.get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                    .strip()
            )
            return transcript

    async def transcribe_stream(self, chunks, on_partial=None):
        params={'model':'nova-3','language':cfg.whisper_language or 'multi',
                'encoding':'linear16','sample_rate':'16000','channels':'1',
                'interim_results':'true','smart_format':'true'}
        from urllib.parse import urlencode
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=100,sock_connect=10)) as session:
            async with session.ws_connect('wss://api.deepgram.com/v1/listen?'+urlencode(params),headers={'Authorization':'Token '+cfg.deepgram_api_key}) as socket:
                finals=[]
                async def receive():
                    async for message in socket:
                        if message.type!=aiohttp.WSMsgType.TEXT:continue
                        import json
                        value=json.loads(message.data)
                        if value.get('type')=='Error':raise RuntimeError(value.get('description','Transcription failed'))
                        if value.get('type')=='Results':
                            alternatives=value.get('channel',{}).get('alternatives',[])
                            text=alternatives[0].get('transcript','').strip() if alternatives else ''
                            if text and value.get('is_final'):finals.append(text)
                            if text and on_partial:on_partial(' '.join(finals if value.get('is_final') else finals+[text]))
                receiver=asyncio.create_task(receive())
                try:
                    async for chunk in chunks:
                        await socket.send_bytes(chunk)
                    await socket.send_json({'type':'CloseStream'})
                    await asyncio.wait_for(receiver,timeout=10)
                    return ' '.join(finals).strip()
                finally:
                    receiver.cancel()
                    await asyncio.gather(receiver,return_exceptions=True)
