# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.1.x   | :white_check_mark: |
| 1.0.x   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in Clicky, please report it responsibly.

**Do NOT open a public issue.** Instead, email:

**shashanksingh2338@gmail.com**

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment**: within 48 hours
- **Assessment**: within 1 week
- **Fix release**: as soon as a patch is ready (typically within 2 weeks for critical issues)

## Scope

The following are in scope:
- The Clicky Windows application (`main.py` and all bundled modules)
- The installer (`Setup-Clicky.exe`)
- API key handling and `.env` file processing
- Network requests made by the web search and AI provider modules

The following are out of scope:
- Third-party services (Ollama, OpenAI, Anthropic, DuckDuckGo)
- The user's local operating system configuration
- Vulnerabilities that require physical access to the machine

## Security Design

- **No telemetry** — Clicky sends zero data home. All usage stays on your machine.
- **API keys stored locally** — keys live in `.env` in the install directory, never transmitted except to their intended provider.
- **Local-first AI** — the default path uses Ollama (fully offline). Cloud providers are opt-in.
- **No auto-update** — the app never phones home for updates. Users download new versions manually from GitHub Releases.

Thank you for helping keep Clicky safe for everyone.
