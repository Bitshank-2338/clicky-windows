"""
Example skill — demonstrates the SKILL interface.

Trigger:  "self mode" / "allow clicks" / "click for me"
Action:   asks Clicky's manager to actually click the next pointed element
          instead of just hovering on it.

Copy this file to ~/.clicky/skills/ and edit, or write your own.
"""

from __future__ import annotations


async def handle_self_mode(manager, transcript: str) -> str:
    # Toggle a flag the overlay/manager could read on the next point_at.
    # (Manager-level click-through is your own responsibility — this is a
    #  template showing how to wire the trigger up.)
    setattr(manager, "_self_mode_armed", True)
    return "Self mode armed. I'll click the next thing I point at."


SKILL = {
    "name":        "Self Mode",
    "trigger":     r"\b(self\s*mode|allow\s*clicks|click\s*for\s*me)\b",
    "description": "Lets Clicky click the element it points at.",
    "handler":     handle_self_mode,
}
