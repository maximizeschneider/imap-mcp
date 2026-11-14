"""Throwaway MCP Apps spike: does Claude Desktop render a ui:// panel from a local
.mcpb server, hide app-only tools from the model, and keep values typed into the
panel out of the conversation? No mail, no real credentials."""

import sys
from pathlib import Path

import keyring
from mcp.server.fastmcp import FastMCP

PANEL_URI = "ui://mailbox-spike/panel.html"
APP_MIME = "text/html;profile=mcp-app"
APP_ONLY = {"ui": {"visibility": ["app"]}}

mcp = FastMCP("mailbox-spike")

_stored: list[int] = []  # lengths only - the value itself is never kept or returned
_items = ["projekt-a@example.com", "projekt-b@example.com", "projekt-c@example.com"]


def log(msg: str) -> None:
    # stderr ends up in Claude Desktop's mcp-server-*.log
    print(f"[mailbox-spike] {msg}", file=sys.stderr, flush=True)


@mcp.resource(PANEL_URI, name="Mailbox spike panel", mime_type=APP_MIME)
def panel() -> str:
    return (Path(__file__).parent / "panel.html").read_text(encoding="utf-8")


@mcp.tool(
    description="Open the mailbox management test panel.",
    meta={"ui": {"resourceUri": PANEL_URI, "visibility": ["model", "app"]}},
)
def open_test_panel() -> str:
    log("open_test_panel")
    return "The test panel is shown to the user. Do not ask for any values; the user enters them in the panel."


@mcp.tool(description="Report what the spike server received, without revealing any values.")
def spike_status() -> str:
    log("spike_status")
    lengths = ", ".join(str(n) for n in _stored) or "none"
    return f"Values received from panel: {len(_stored)} (lengths: {lengths}). Remaining items: {', '.join(_items) or 'none'}."


@mcp.tool(description="Write, read back and delete a dummy OS keychain entry.")
def keyring_check() -> str:
    log("keyring_check")
    service, user = "imap-slim-spike", "probe"
    try:
        backend = type(keyring.get_keyring()).__name__
        keyring.set_password(service, user, "probe-value")
        ok = keyring.get_password(service, user) == "probe-value"
        keyring.delete_password(service, user)
        gone = keyring.get_password(service, user) is None
    except Exception as e:  # spike: report any backend failure verbatim
        return f"Keychain FAILED: {type(e).__name__}: {e}"
    return f"Keychain backend {backend}: write/read {'OK' if ok else 'MISMATCH'}, delete {'OK' if gone else 'FAILED'}."


@mcp.tool(description="Store a value typed into the panel.", meta=APP_ONLY)
def store_value(value: str) -> str:
    _stored.append(len(value))
    log(f"store_value: received {len(value)} chars")
    return f"Stored ({len(value)} characters)."


@mcp.tool(description="List items for the panel.", meta=APP_ONLY)
def list_items() -> list[str]:
    log("list_items")
    return _items


@mcp.tool(description="Remove an item from the panel.", meta=APP_ONLY)
def remove_item(item: str) -> str:
    log(f"remove_item: {item}")
    if item in _items:
        _items.remove(item)
        return f"Removed {item}."
    return f"Not found: {item}."


if __name__ == "__main__":
    mcp.run()
