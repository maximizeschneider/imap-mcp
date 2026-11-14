"""Desktop extension manifest: install needs no input, mailboxes come from the panel."""

import json
from pathlib import Path

MANIFEST = json.loads((Path(__file__).resolve().parents[2] / "imap-slim" / "manifest.json").read_text())


def test_server_and_port_are_optional_with_office_defaults():
    cfg = MANIFEST["user_config"]
    assert cfg["server"]["default"] == "192.168.0.110"
    assert cfg["port"]["default"] == 993
    assert not any(field.get("required") for field in cfg.values())


def test_no_credentials_in_the_install_form():
    assert set(MANIFEST["user_config"]) == {"server", "port"}


def test_env_enables_the_panel_and_passes_the_server():
    env = MANIFEST["server"]["mcp_config"]["env"]
    assert env == {
        "IMAP_SLIM_SERVER": "${user_config.server}",
        "IMAP_SLIM_PORT": "${user_config.port}",
        "IMAP_SLIM_MAILBOX_PANEL": "1",
    }


def test_declared_tools_are_the_model_visible_ones():
    assert [t["name"] for t in MANIFEST["tools"]] == ["use_mail", "manage_mailboxes"]


def test_extension_page_explains_setup_like_the_panel():
    """Clients read the extension page before they ever open the panel."""
    text = MANIFEST["long_description"]
    assert "Postfächer verwalten" in text
    assert "„Konto bearbeiten“" in text
