"""Separate narration from Clicky's declarative JSON in a token stream."""
import json


class ResponseBlocks:
    MARKERS = {"```clicky-scene": "scene", "```clicky-drive": "drive", "```clicky-browser": "browser", "```clicky-tool": "tool"}

    def __init__(self):
        self.pending = ""
        self.kind = None

    def feed(self, chunk):
        self.pending += chunk
        visible, blocks = [], []
        while self.pending:
            if self.kind:
                end = self.pending.find("```")
                if end < 0:
                    if len(self.pending) > 100000:
                        raise ValueError("Clicky structured response exceeded its size limit")
                    break
                blocks.append((self.kind, json.loads(self.pending[:end].strip())))
                self.pending, self.kind = self.pending[end + 3:], None
            else:
                found = [(self.pending.find(marker), marker) for marker in self.MARKERS if marker in self.pending]
                if found:
                    start, marker = min(found)
                    visible.append(self.pending[:start])
                    self.pending, self.kind = self.pending[start + len(marker):], self.MARKERS[marker]
                else:
                    keep = max([n for marker in self.MARKERS for n in range(1, len(marker)) if self.pending.endswith(marker[:n])] or [0])
                    visible.append(self.pending[:-keep] if keep else self.pending)
                    self.pending = self.pending[-keep:] if keep else ""
                    break
        return "".join(visible), blocks

    def finish(self):
        if self.kind:
            raise ValueError("Incomplete Sketch/Drive block; no actions were executed")
        pending, self.pending = self.pending, ""
        return pending
