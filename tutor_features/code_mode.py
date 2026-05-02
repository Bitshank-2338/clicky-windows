"""
Code mode — when active window is an IDE, swap the tutor prompt for a
coding-focused one.

Detection: window title regex match against common IDEs / editors:
    VS Code, Visual Studio, IntelliJ, PyCharm, WebStorm, Cursor, Zed,
    Sublime, Vim, Neovim, Notepad++, Eclipse, Xcode, Android Studio
"""

import re

IDE_PATTERNS = re.compile(
    r"(visual\s+studio\s+code|^vs\s*code|cursor|"
    r"intelliJ|pycharm|webstorm|phpstorm|rubymine|goland|datagrip|clion|"
    r"android\s+studio|xcode|"
    r"sublime\s+text|notepad\+\+|emacs|"
    r"\b(vim|nvim|neovim)\b|"
    r"zed|fleet|"
    r"eclipse|netbeans|"
    r"\.py\b|\.ts\b|\.tsx\b|\.js\b|\.go\b|\.rs\b|\.java\b|\.cpp\b)",
    re.IGNORECASE,
)


def is_code_window(window_title: str) -> bool:
    if not window_title:
        return False
    return IDE_PATTERNS.search(window_title) is not None


def code_system_prompt_addendum() -> str:
    """Appended to the normal system prompt when the active window is an IDE."""
    return (
        "\n\nCODE CONTEXT: The user is in an IDE/editor. Treat them as a "
        "developer learning. When they ask about visible code:\n"
        "  • Identify the language from syntax\n"
        "  • Explain what the code DOES, not just what each line says\n"
        "  • Spot bugs, anti-patterns, missing edge cases proactively\n"
        "  • Suggest one concrete improvement at the end\n"
        "  • For error messages: explain WHY it failed and how to fix\n"
        "  • Use exact identifier names from the screenshot (case-sensitive)\n"
        "Skip generic 'this is a function' filler — they can see that."
    )
