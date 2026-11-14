# Mailbox panel in the Desktop extension

Frame: `2026-10-27-frame-mcpb-multi-account.md`. Spike: `../research/2026-10-27-mcp-apps-spike/`.

## Problem

The `.mcpb` holds one mailbox, entered in the install form. The target users have one mailbox per project on one server and no IT skills; `setup.py` is not an option for them.

## Goal

Install needs no input (server and port preset, editable). Mailboxes are added, re-passworded and removed in an MCP Apps panel inside the chat. Passwords never pass through the model. Removal only by a human click.

## Intent and constraints

- Keychain is the only state: model calls and panel calls reach different server processes (spike finding).
- The panel is re-created by the host on scroll; it loads everything from the server on mount.
- App-only tools are hidden from the model by Claude Desktop (spike). Other hosts may show them, so they are registered only when `IMAP_SLIM_MAILBOX_PANEL=1`, which only the `.mcpb` manifest sets.
- Panel accounts store no server/port: they fall back to `IMAP_SLIM_SERVER`/`IMAP_SLIM_PORT`, so a later server change in the extension settings applies to all mailboxes. IMAP on the target server is currently unreachable (frame blocker) - the address may still change.
- Sandboxed iframe: no `confirm()` (no allow-modals); confirmation is in-panel, two-step.
- Default CSP allows inline scripts only: the vendored ext-apps bundle (2.0.4) is inlined when the resource is read.
- No connection test on save (server unreachable today; would hang the panel). Out of scope: STARTTLS/143, cert pinning, set-default button, rename.

## Acceptance Criteria

- [x] AC1: Manifest: server and port optional, defaults `192.168.0.110` and `993`; no username/password/from fields; sets `IMAP_SLIM_MAILBOX_PANEL=1`.
- [x] AC2: Keychain accounts without stored server/port use the env server/port.
- [x] AC3: `mailboxes` module: list (no passwords), save (new needs password; existing keeps password when empty), remove (default moves to first remaining), remove all. setup.py uses it for save/remove/clear.
- [x] AC4: With the env flag, the server exposes `manage_mailboxes` (`ui.resourceUri`, visibility model+app) and app-only `mailbox_list`, `mailbox_save`, `mailbox_remove`, `mailbox_remove_all`; the `ui://` resource is served as `text/html;profile=mcp-app` with the bundle inlined. Without the flag none of them exist.
- [x] AC5: Panel: shows server, lists mailboxes, add form (address, username, password), change password, remove and remove-all with in-panel confirmation; errors shown; works against a fake host in Chromium.
- [x] AC6: "Not configured" messages point to the panel when the flag is set.
- [x] AC7: Docs, version 2.4.0, rebuilt `releases/mailbox-2.4.0.mcpb`.

```gherkin
Scenario: install without input
  Given the extension is installed with all form fields left as they are
  Then IMAP_SLIM_SERVER is "192.168.0.110" and IMAP_SLIM_PORT is "993"

Scenario: add a mailbox
  Given no accounts in the keychain
  When the panel saves address "p1@firma.de", username "p1", password "x"
  Then accounts is ["p1@firma.de"], it is the default, from_address is "p1@firma.de"
  And get_credentials("p1@firma.de") returns the env server and port

Scenario: change password keeps it when empty
  Given account "p1@firma.de" with password "x"
  When the panel saves it with username "p1b" and an empty password
  Then the username is "p1b" and the password is still "x"

Scenario: new mailbox without password
  When the panel saves a new address with an empty password
  Then the call fails with "Passwort fehlt" and nothing is stored

Scenario: remove the default
  Given accounts a (default) and b
  When the panel removes a
  Then accounts is [b], default is b, no key of a remains

Scenario: remove all
  When the panel removes all
  Then no key under service "imap-slim" remains

Scenario: tools hidden outside the extension
  Given IMAP_SLIM_MAILBOX_PANEL is unset
  Then the server lists only use_mail
```

## Tasks

- [x] 1. Tests + `mailboxes.py` (AC3), setup.py delegates.
- [x] 2. Tests + env fallback in `get_credentials` (AC2).
- [x] 3. Tests + `mailbox_panel.py` registration, resource, vendored bundle (AC4); wire into `imap_stream_mcp.py`.
- [x] 4. Panel HTML (AC5), fake-host Chromium check.
- [x] 5. Messages (AC6), manifest (AC1) + test.
- [x] 6. Verify: full imap-slim suite, ruff, pack, run packed server with an MCP client.
- [x] 7. Docs, versions, bundle (AC7).

- [+] 8. Review fixes: edit keeps a custom From; existing non-address accounts editable; per-account server shown; missing server named in the error; robust bridge inlining.

## Decisions during implementation

- Kept the `192.168.0.110` default despite review finding (ships to every .mcpb user): HC's explicit requirement; this fork is built for HC's clients.
- Old Desktop-form single account not migrated: CHANGELOG tells extension users to re-add it in the panel.
- No lock around the accounts JSON: concurrent saves from two panels are unlikely; noted.

## Testing

pytest in `tests/imap-slim/` with the `fake_keyring` fixture; no network. Panel: Playwright against a fake postMessage host (scratch script, not in the suite). Manual on HC's Mac after release.
