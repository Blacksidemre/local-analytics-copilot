# Security Policy

## Supported version

Security fixes currently target the latest `1.0.0rc*` release. No earlier build should be used with
real company or personal data.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting/security-advisory flow for this repository. Do not open
a public issue containing credentials, personal data, confidential documents, exploit payloads or
unredacted logs. Include the affected version, minimal reproduction, impact and suggested mitigation.

## Default security boundary

- Keep the service on `127.0.0.1` unless an explicit private-network design has been reviewed.
- Use an API token for any non-loopback access.
- Use a technically read-only database account; the application SQL parser is defense-in-depth.
- Keep web access, remote Ollama and cloud model tags disabled for confidential workloads.
- Inspect every queued write/external action before approval.
- Never commit `.env`, `workspace/knowledge`, datasets, outputs, logs or SQLite state.

This project is analytics software, not a substitute for OS isolation, database permissions, firewall,
DLP, KVKK/GDPR controls or organizational review.
