"""Incremental sentence boundaries, keeping drawing tags with their narration."""
import re


class SentenceBuffer:
    def __init__(self):
        self.pending = ""

    def feed(self, chunk):
        self.pending += chunk
        result = []
        while True:
            # A tag immediately after punctuation still belongs to that sentence.
            match = re.search(r"[.!?](?:\s*\[[^\]]*\])*\s+(?=[^\s\[])", self.pending)
            if not match:
                return result
            result.append(self.pending[:match.end()].strip())
            self.pending = self.pending[match.end():]

    def finish(self):
        pending, self.pending = self.pending.strip(), ""
        return [pending] if pending else []
