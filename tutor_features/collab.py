"""
Live collaboration — share a Clicky session with a friend over WebRTC.

Status: SKELETON. The mechanism is laid out, but a working build needs:
  1. A signalling server (WebSocket relay so peers can find each other)
     — easiest free option: PeerJS Cloud or a 50-line Cloudflare Worker.
  2. Implement the data-channel send/recv loop using `aiortc`.
  3. Wire CompanionManager.sig_response_chunk + sig_point_at to broadcast,
     and consume incoming messages on the receiver side.

Why it's a skeleton: WebRTC + NAT traversal + state sync needs careful
testing across two machines on different networks — we can't validate that
in a single coding session. Ship this when you have time to iterate.

How users would use it once finished:
    ┌─ HOST ─────────────────────────┐    ┌─ FRIEND ──────────────────────┐
    │ Tray → Live Session → Start    │    │ Tray → Live Session → Join    │
    │ Tray shows code:  BLU-X4F      │    │ Pop-up: "Enter code:"         │
    │ Friend clicks Join              │    │ Types  BLU-X4F                │
    │ Both Clickys now share:         │    │ Both Clickys now share:       │
    │   • LLM responses               │    │   • LLM responses             │
    │   • Pointer coordinates         │    │   • Pointer coordinates       │
    │   • Q&A history                 │    │   • Q&A history               │
    └────────────────────────────────┘    └────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import secrets
import string
from typing import Callable, Optional


def generate_code() -> str:
    """6-char human-readable code, e.g. 'BLU-X4F'."""
    alphabet = string.ascii_uppercase + string.digits
    a = "".join(secrets.choice(alphabet) for _ in range(3))
    b = "".join(secrets.choice(alphabet) for _ in range(3))
    return f"{a}-{b}"


class CollabSession:
    """Stub for a peer-to-peer session.

    When `aiortc` is installed and a signalling URL is configured, this
    becomes a real WebRTC data-channel session. Until then, calling start()
    just generates a code and logs that the session would have started.
    """

    SIGNALLING_URL = "wss://clicky-signal.example/v1"   # TODO: stand up server

    def __init__(self):
        self.code: Optional[str] = None
        self.is_host: bool = False
        self.peers: list = []
        self._on_message: Optional[Callable[[dict], None]] = None
        self._pc = None      # aiortc.RTCPeerConnection
        self._channel = None # aiortc.RTCDataChannel

    async def start_host(self) -> str:
        """Create a session, register with the signalling server, return code."""
        self.code = generate_code()
        self.is_host = True
        # TODO: connect to SIGNALLING_URL, register self.code, await join, set up
        # RTCPeerConnection + data channel, plumb _on_message.
        return self.code

    async def join(self, code: str) -> bool:
        """Connect to an existing session by code. Returns success."""
        self.code = code
        self.is_host = False
        # TODO: connect to SIGNALLING_URL, request offer for `code`, accept,
        # set local description, exchange ICE, plumb _on_message.
        return False

    async def send(self, msg: dict) -> None:
        """Broadcast a message to all peers in the session."""
        # TODO: when self._channel.readyState == "open", send JSON
        pass

    async def stop(self) -> None:
        """Tear down peer connection."""
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
        if self._pc:
            try:
                await self._pc.close()
            except Exception:
                pass
        self.code = None
        self.peers = []

    def on_message(self, callback: Callable[[dict], None]) -> None:
        """Register a callback for incoming messages from peers."""
        self._on_message = callback
