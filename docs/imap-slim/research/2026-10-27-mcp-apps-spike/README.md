# MCP Apps spike (throwaway)

Question: can the Desktop extension manage many mailboxes in an MCP Apps panel, with passwords never reaching the model?

Build: `python3 build.py && npx @anthropic-ai/mcpb pack . mailbox-spike-0.1.0.mcpb`

Verified in the cloud session (2026-10-27):
- Server lists tools with `_meta.ui` (resourceUri, `visibility: ["app"]`), serves `ui://mailbox-spike/panel.html` as `text/html;profile=mcp-app`, from the packed bundle too.
- Panel (ext-apps 2.0.4, inlined) completes `ui/initialize` and calls app-only tools against a fake host in Chromium.
- Keychain: no backend in the Linux container (expected) - says nothing about macOS/Windows.

Checks on Claude Desktop (HC):
1. Panel renders in chat after "Öffne das Test-Panel".
2. Model does not see `store_value`, `list_items`, `remove_item`.
3. Canary `KANARIE-4711` typed in the panel does not appear in Claude's context or the transcript; `spike_status` reports its length only.
4. `keyring_check` passes on the target OS.

Results (HC, Claude Desktop, OS presumably macOS - backend class `Keyring`):
- Check 2 PASS: model lists only open_test_panel, spike_status, keyring_check.
- Check 4 PASS: keychain write/read/delete OK.
- Check 1 PASS: panel renders inline, status "Verbunden mit Claude 1.0.0". App-only calls work: store_value (13 and 3 chars), remove_item x3.
- Check 3 PASS (model side): model could not name the values; app-only calls do not show as tool calls in the chat. Not verifiable from the UI: server-side storage of app call arguments.
- Finding: model-called spike_status still reported 0 values and 3 items after the panel had changed both. Model calls and panel calls most likely reach different server processes. Design consequence: no in-process state; keychain is the only shared state.
- Finding: panel log lines vanish when scrolling away - the host re-creates the iframe. Panel must load all state from the server on every mount (list does: shows "Keine Einträge").
