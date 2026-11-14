"""Mailbox management panel (MCP Apps) for the Claude Desktop extension.

The panel lets a user add, re-password and remove mailboxes without a terminal.
Editing tools are app-only: Claude Desktop hides them from the model, so
passwords typed into the panel never enter the conversation and removal takes
a human click - a crafted mail cannot make the model delete accounts. Hosts
without MCP Apps would list them to the model, hence registration only when
the .mcpb sets IMAP_SLIM_MAILBOX_PANEL.

Model calls and panel calls may reach different server processes, so no state
lives here: every call reads and writes the keychain.
"""

from functools import cache, wraps
from pathlib import Path
from typing import Any

import imap_client
import mailboxes

PANEL_URI = "ui://imap-slim/mailboxes.html"
APP_MIME = "text/html;profile=mcp-app"
APP_ONLY = {"ui": {"visibility": ["app"]}}

_HERE = Path(__file__).parent
_BRIDGE = _HERE / "vendor" / "ext-apps-2.0.4-app-with-deps.js"
_PANEL = _HERE / "panel" / "mailboxes.html"


@cache
def panel_html() -> str:
    """Panel with the ext-apps bridge inlined.

    The default MCP Apps CSP allows inline scripts only. The bridge is an ES
    module ending in a single export list; it is turned into a global so the
    panel's own inline script can use it.
    """
    bridge = _BRIDGE.read_text(encoding="utf-8").rstrip()
    start = bridge.rindex("export{")
    names = []
    for item in bridge[start + len("export{") : bridge.rindex("}")].split(","):
        local, _, alias = item.partition(" as ")
        names.append(f"{alias or local}:{local}")
    bridge = bridge[:start] + "window.McpApps={" + ",".join(names) + "};"
    lowered = bridge.lower()
    if "</script" in lowered or "<!--" in lowered:
        raise RuntimeError("bridge cannot be inlined into a <script> element")
    return _PANEL.read_text(encoding="utf-8").replace("/*__EXT_APPS__*/", bridge)


def _server_label() -> str:
    server = imap_client._env("SERVER")
    return f"{server}:{imap_client._env('PORT') or '993'}" if server else ""


FAILED = (
    "Das hat nicht geklappt. Bitte versuchen Sie es noch einmal. Wenn es weiterhin nicht klappt, "
    "wenden Sie sich an die Person, die Ihnen die Erweiterung eingerichtet hat."
)


def _plain_errors(fn):
    """Show the panel user a plain German message; technical detail goes below it.

    ValueErrors from mailboxes are already written for the user. Anything else
    (a locked keychain, a missing backend) is not, but whoever helps the user
    needs it - the panel renders the part after "Technische Meldung" small.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"{FAILED}\nTechnische Meldung: {type(e).__name__}: {e}") from e

    return wrapper


def register(mcp) -> None:
    """Add the panel resource and its tools to a FastMCP server."""

    @mcp.resource(PANEL_URI, name="Mailboxes", mime_type=APP_MIME)
    def panel() -> str:
        return panel_html()

    @mcp.tool(
        title="Postfächer verwalten",
        description="Open the panel where the user adds, changes or removes mailboxes. Use when the user wants to set up a mailbox or no account is configured.",
        meta={"ui": {"resourceUri": PANEL_URI, "visibility": ["model", "app"]}},
    )
    def manage_mailboxes() -> str:
        return "The mailbox panel is shown to the user. Never ask for passwords in chat: the user enters them in the panel."

    @mcp.tool(description="Server and mailboxes for the panel.", meta=APP_ONLY)
    @_plain_errors
    def mailbox_list() -> dict[str, Any]:
        return {"server": _server_label(), "mailboxes": mailboxes.list_mailboxes()}

    @mcp.tool(description="Add a mailbox or change its login.", meta=APP_ONLY)
    @_plain_errors
    def mailbox_save(address: str, username: str, password: str = "") -> str:
        mailboxes.save_mailbox(address, username, password)
        return f"Das Postfach {address.strip()} wurde gespeichert."

    @mcp.tool(description="Remove a mailbox.", meta=APP_ONLY)
    @_plain_errors
    def mailbox_remove(address: str) -> str:
        mailboxes.remove(address)
        return f"Das Postfach {address} wurde entfernt."

    @mcp.tool(description="Remove all mailboxes.", meta=APP_ONLY)
    @_plain_errors
    def mailbox_remove_all() -> str:
        mailboxes.remove_all()
        return "Alle Zugangsdaten wurden von diesem Computer gelöscht."
