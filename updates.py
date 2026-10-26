"""Explicit GitHub release updates with digest verification; never runs a download silently."""
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from storage import data_dir

VERSION='1.6.0-preview'
REPOSITORY='Bitshank-2338/clicky-windows'


def version_key(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-([A-Za-z0-9.-]+))?',value)
    if not match:raise ValueError('Unrecognized release version')
    return (*map(int,match.groups()[:3]),0 if match.group(4) else 1)


async def latest():
    async with httpx.AsyncClient(timeout=20) as client:
        response=await client.get(f'https://api.github.com/repos/{REPOSITORY}/releases/latest',headers={'Accept':'application/vnd.github+json'})
        response.raise_for_status()
        release=response.json()
    if version_key(release['tag_name'])<=version_key(VERSION):return None
    assets=[asset for asset in release.get('assets',[]) if asset['name'].lower().endswith('.exe')]
    return {'version':release['tag_name'],'url':release['html_url'],'asset':assets[0] if assets else None}


async def download(asset):
    url=asset['browser_download_url']
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='github.com' or not parsed.path.startswith('/'+REPOSITORY+'/releases/download/'):
        raise ValueError('Update download is outside the Clicky release repository')
    digest=asset.get('digest','')
    if not re.fullmatch(r'sha256:[0-9a-fA-F]{64}',digest):
        raise ValueError('This release has no verified SHA-256 digest; use the release page instead')
    name=asset['name']
    if Path(name).name!=name or not name.lower().endswith('.exe'):
        raise ValueError('Invalid installer filename')
    directory=data_dir()/'updates';directory.mkdir(exist_ok=True)
    path=directory/name
    temporary=path.with_suffix('.part')
    hashed=hashlib.sha256();size=0
    try:
        async with httpx.AsyncClient(timeout=120,follow_redirects=True) as client:
            async with client.stream('GET',url) as response:
                response.raise_for_status()
                with temporary.open('wb') as stream:
                    async for chunk in response.aiter_bytes():
                        size+=len(chunk)
                        if size>1_500_000_000:raise ValueError('Update exceeds the size limit')
                        hashed.update(chunk);stream.write(chunk)
        if hashed.hexdigest()!=digest[7:].lower():raise ValueError('Update checksum did not match; installer was not saved')
        temporary.replace(path)
        return str(path)
    finally:temporary.unlink(missing_ok=True)
