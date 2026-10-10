# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | Yes |

## Reporting a vulnerability

Email **kyaw.tech@gmail.com** with a description and steps to reproduce. Expect an
acknowledgement within 3 business days. Please do not open a public issue for
vulnerabilities until a fix is released.

## Scope notes

- Dev API keys in `.env.example` are placeholders; `enterprise` deployment mode
  refuses them by design.
- The guardrail engine is a default-deny aid, not a security boundary — always
  enforce authorization in your own agent before acting on tool output.
