# Frame: many mailboxes in the Desktop extension

Status: framing (HC in the loop, no "go" yet)

## Need

- User without IT skills, Claude Desktop, installs `mailbox-<version>.mcpb`.
- One mailbox per project at the same provider: same IMAP server, own username + password + address each.
- Count: "many", grows when new projects start.
- Webmail browser logins are irrelevant: IMAP needs the mailbox credentials.

## Current state

- `.mcpb` maps one `user_config` set to `IMAP_SLIM_*` env (`imap-slim/manifest.json`).
- `get_credentials` falls back to that single env set when the keychain holds no accounts (`imap-slim/imap_client.py`).
- Multi-account exists only via keychain, filled by `setup.py` (terminal) - not usable by the target user.

## Constraints (MCPB manifest spec)

- `user_config` types: string, number, boolean, directory, file. `multiple` only for directory/file - no repeatable string groups.
- No documented field limit. Fields optional unless `required: true`. `sensitive` masks and stores securely.
- Password must never pass through the LLM (existing design rule).

## Options

- A. Fixed slots in the form: shared server/port, then N x (address, username, password). Small code change (env parsing `IMAP_SLIM_<n>_*`). Form grows 3 fields per slot; hard cap N; new project = edit extension settings.
- B. Setup page from chat: action opens a one-shot local page (127.0.0.1, random token) in the browser; person enters address/username/password; stored in OS keychain like `setup.py`. Unlimited, addable anytime, password bypasses the LLM. More code; local server and keychain under Desktop runtime are risks to verify.
- Hybrid: form holds server (+ first mailbox), more mailboxes via B.

## Option B: managing mailboxes (proposal)

- One local page for add, change password and remove; opened from chat ("Postfächer verwalten").
- Removal only by a human click on that page, never as an LLM tool action - a crafted mail could otherwise make Claude delete accounts.
- Uninstalling the extension does not touch the OS keychain: the page needs "Alle entfernen" before uninstall.
- Fallback: OS keychain app, entries under service "imap-slim".

## Option C: MCP Apps (UI inside the chat)

- MCP Apps extension: tool points to a `ui://` HTML resource, host renders it in a sandboxed iframe; tools with `_meta.ui.visibility: ["app"]` are callable from the UI and hidden from the model.
- Fits list/add/remove: remove as app-only tool = human click, not model action.
- Unverified: Claude Desktop renders Apps from a local `.mcpb` server; app-only calls (with password) stay out of model context and transcript; Python `mcp` SDK version (repo pins `mcp>=1.0,<2`, FastMCP).
- Spec rule: elicitation form mode MUST NOT request passwords; URL mode MUST be used for them. Apps is a different mechanism, but the same concern applies - password entry needs proof it bypasses the model.
- Spike done (`docs/imap-slim/research/2026-10-27-mcp-apps-spike/`): renders from local `.mcpb` on macOS, app-only tools hidden and callable, keychain works. Model and panel calls likely hit different server processes - keychain must be the only state.

## Direction (proposed, awaiting HC)

- Option C. Server/port preset (HC: 192.168.0.110:993) so clients enter nothing at install; panel manages mailboxes (add, change password, remove, remove all) via app-only tools writing the keychain; model tool opens the panel.
- Keep env single-account fallback for existing 2.2.0 installs.

## Risks of the preset server (HC decision 2026-10-27)

- 192.168.0.110 is a private LAN address. HC: clients use mail only in the office network - accepted.
- TLS: `IMAPClient(..., ssl=True)` verifies certificate and hostname by default. A certificate issued for a hostname, or self-signed, fails against a bare IP. Unverified for this server.
- The repo is a public fork: customer address belongs in a build-time setting, not the generic manifest.

## Blocker (2026-10-27)

- HC: port 993 on 192.168.0.110 is not reachable; only the webmail (HTTP, port 80) works.
- imap-slim speaks IMAP only. Without IMAP access nothing in this frame works - planning paused.
- Webmail usually reads mail server-side via IMAP on the same machine, so IMAP likely exists but is disabled, bound to localhost, or firewalled.
- Next: identify mail server product; probe ports 143/993; enable IMAP (prefer 993 with TLS) on the server.

## Open questions

- Which certificate does 192.168.0.110:993 present (hostname, self-signed)? Proposed if self-signed: pin its SHA-256 fingerprint at build time instead of disabling verification. Webmail runs plain HTTP on the same IP - says nothing about the IMAP certificate.

- Rough mailbox count now and per year?
- Who adds a new project mailbox: the person or a helper?
- Does Claude Desktop let users edit extension settings after install (needed for A)?
