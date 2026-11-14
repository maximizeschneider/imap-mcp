"""MCP Apps mailbox panel for the Desktop extension."""

import importlib
import json

import pytest
from mcp.server.fastmcp import FastMCP

pytestmark = pytest.mark.anyio

APP_TOOLS = {"mailbox_list", "mailbox_save", "mailbox_remove", "mailbox_remove_all"}


@pytest.fixture
def server(fake_keyring, monkeypatch):
    import mailbox_panel

    monkeypatch.setenv("IMAP_SLIM_SERVER", "192.168.0.110")
    monkeypatch.setenv("IMAP_SLIM_PORT", "993")
    mcp = FastMCP("t")
    mailbox_panel.register(mcp)
    return mcp


async def call(mcp, name, args=None):
    _content, structured = await mcp.call_tool(name, args or {})
    # str results are wrapped as {"result": ...}; dict results are the structured content itself.
    return structured.get("result", structured)


class TestRegistration:
    async def test_opener_points_at_the_panel_and_stays_visible_to_the_model(self, server):
        import mailbox_panel

        tools = {t.name: t for t in await server.list_tools()}

        ui = tools["manage_mailboxes"].meta["ui"]
        assert ui["resourceUri"] == mailbox_panel.PANEL_URI
        assert ui["visibility"] == ["model", "app"]

    async def test_editing_tools_are_app_only(self, server):
        """Claude Desktop hides these from the model, so removal needs a human click."""
        tools = {t.name: t for t in await server.list_tools()}

        assert APP_TOOLS <= tools.keys()
        for name in APP_TOOLS:
            assert tools[name].meta == {"ui": {"visibility": ["app"]}}, name

    async def test_panel_resource_is_an_mcp_app_with_the_bridge_inlined(self, server):
        import mailbox_panel

        (res,) = await server.list_resources()
        assert str(res.uri) == mailbox_panel.PANEL_URI
        assert res.mimeType == "text/html;profile=mcp-app"

        (contents,) = await server.read_resource(mailbox_panel.PANEL_URI)
        html = contents.content
        assert contents.mime_type == "text/html;profile=mcp-app"
        assert html.startswith("<!doctype html>")
        assert "window.McpApps={" in html
        assert "__EXT_APPS__" not in html
        # The default MCP Apps CSP blocks every external source.
        assert "<script src" not in html


class TestEnvFlag:
    """Only the .mcpb sets the flag; hosts without MCP Apps would show app-only tools to the model."""

    def reload(self, monkeypatch, value):
        if value is None:
            monkeypatch.delenv("IMAP_SLIM_MAILBOX_PANEL", raising=False)
        else:
            monkeypatch.setenv("IMAP_SLIM_MAILBOX_PANEL", value)
        import imap_stream_mcp

        return importlib.reload(imap_stream_mcp)

    async def test_without_flag_only_use_mail(self, monkeypatch):
        mod = self.reload(monkeypatch, None)
        assert [t.name for t in await mod.mcp.list_tools()] == ["use_mail"]

    async def test_with_flag_panel_tools_exist(self, monkeypatch):
        mod = self.reload(monkeypatch, "1")
        names = {t.name for t in await mod.mcp.list_tools()}
        assert names == {"use_mail", "manage_mailboxes"} | APP_TOOLS
        self.reload(monkeypatch, None)


class TestTools:
    async def test_list_reports_server_and_mailboxes(self, server):
        await call(server, "mailbox_save", {"address": "p1@firma.de", "username": "p1", "password": "x"})

        state = await call(server, "mailbox_list")

        assert state == {
            "server": "192.168.0.110:993",
            "mailboxes": [{"address": "p1@firma.de", "username": "p1", "default": True, "server": None}],
        }

    async def test_save_never_echoes_the_password(self, server):
        message = await call(server, "mailbox_save", {"address": "p1@firma.de", "username": "p1", "password": "geheim-123"})

        assert "geheim-123" not in json.dumps(message)
        assert "p1@firma.de" in message

    async def test_save_errors_reach_the_panel(self, server):
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Passwort fehlt"):
            await call(server, "mailbox_save", {"address": "p1@firma.de", "username": "p1", "password": ""})

    async def test_remove_and_remove_all(self, server, fake_keyring):
        for n in ("a", "b", "c"):
            await call(server, "mailbox_save", {"address": f"{n}@firma.de", "username": n, "password": "x"})

        await call(server, "mailbox_remove", {"address": "b@firma.de"})
        assert [m["address"] for m in (await call(server, "mailbox_list"))["mailboxes"]] == ["a@firma.de", "c@firma.de"]

        await call(server, "mailbox_remove_all")
        assert (await call(server, "mailbox_list"))["mailboxes"] == []
        assert not fake_keyring.store

    async def test_opener_tells_the_model_not_to_ask_for_passwords(self, server):
        text = await call(server, "manage_mailboxes")
        assert "password" in text.lower()


class TestNotConfiguredPointsToPanel:
    """In the extension there is no setup.py to run; the model should open the panel."""

    async def test_accounts_action(self, fake_keyring, monkeypatch):
        from imap_stream_mcp import MailAction, use_mail

        monkeypatch.setenv("IMAP_SLIM_MAILBOX_PANEL", "1")
        monkeypatch.setenv("IMAP_SLIM_SERVER", "192.168.0.110")
        monkeypatch.delenv("IMAP_SLIM_USERNAME", raising=False)

        result = await use_mail(MailAction(action="accounts"))

        assert "manage_mailboxes" in result
        assert "setup.py" not in result

    def test_credentials_error(self, fake_keyring, monkeypatch):
        import imap_client

        monkeypatch.setenv("IMAP_SLIM_MAILBOX_PANEL", "1")
        monkeypatch.setenv("IMAP_SLIM_SERVER", "192.168.0.110")
        monkeypatch.delenv("IMAP_SLIM_USERNAME", raising=False)

        with pytest.raises(imap_client.IMAPError, match="manage_mailboxes"):
            imap_client.get_credentials()

    def test_credentials_error_without_flag_still_names_setup(self, fake_keyring, monkeypatch):
        import imap_client

        monkeypatch.delenv("IMAP_SLIM_MAILBOX_PANEL", raising=False)
        monkeypatch.delenv("IMAP_SLIM_SERVER", raising=False)

        with pytest.raises(imap_client.IMAPError, match="setup.py"):
            imap_client.get_credentials()
