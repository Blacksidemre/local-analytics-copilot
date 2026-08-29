# Remote Access

The safest default is `lac serve --host 127.0.0.1` so the UI is only reachable on the same computer.

If you want to use the home workstation remotely:
1. Keep the workstation on and logged in according to your own security policy.
2. Use a private encrypted network/VPN solution rather than exposing port 8765 directly to the public internet.
3. Bind the app to a private interface only when required.
4. Use OS firewall rules and strong device/account authentication.
5. Do not move employer/customer data to a home machine unless company policy explicitly allows it.

`lac serve --host 0.0.0.0` is rejected unless both `LAC_ALLOW_NETWORK_BIND=true` and a non-empty
`LAC_API_TOKEN` are configured. Those controls do not make public exposure safe. Do not port-forward
the service from a home router to the public internet.
