"""
Example skill — demonstrates the SKILL interface.

Trigger:  "self mode" / "allow clicks" / "click for me"
Action:   asks Clicky's manager to actually click the next pointed element
          instead of just hovering on it.

Copy this file to ~/.clicky/skills/ and edit, or write your own.
"""

from __future__ import annotations


async def handle_self_mode(manager, transcript: str) -> str:
    return "Tell me the task, for example 'click the Save button for me'. Clicky Drive shows the exact actions for you to approve before it does anything."


SKILL = {
    "name":        "Self Mode",
    "trigger":     r"\b(self\s*mode|allow\s*clicks|click\s*for\s*me)\b",
    "description": "Lets Clicky click the element it points at.",
    "handler":     handle_self_mode,
}
