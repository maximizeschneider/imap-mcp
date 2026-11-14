"""Keychain account store shared by setup.py and the Desktop mailbox panel."""

import json

import pytest

SERVICE = "imap-slim"


@pytest.fixture
def mb(fake_keyring):
    import mailboxes

    return mailboxes


def keys(fake):
    return {k for (s, k) in fake.store if s == SERVICE}


class TestSave:
    def test_first_mailbox_becomes_default_and_its_address_the_from(self, mb, fake_keyring):
        mb.save_mailbox("p1@firma.de", "p1", "x")

        assert json.loads(fake_keyring.get_password(SERVICE, "accounts")) == ["p1@firma.de"]
        assert fake_keyring.get_password(SERVICE, "default_account") == "p1@firma.de"
        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_username") == "p1"
        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_password") == "x"
        assert fake_keyring.get_password(SERVICE, "p1@firma.de:from_address") == "p1@firma.de"

    def test_panel_mailboxes_store_no_server(self, mb, fake_keyring):
        """The server comes from the extension settings, so changing it there reaches every mailbox."""
        mb.save_mailbox("p1@firma.de", "p1", "x")

        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_server") is None
        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_port") is None

    def test_explicit_server_is_stored(self, mb, fake_keyring):
        mb.save("work", "u", "x", server="mail.example.com", port="993", from_address="u@example.com")

        assert fake_keyring.get_password(SERVICE, "work:imap_server") == "mail.example.com"
        assert fake_keyring.get_password(SERVICE, "work:from_address") == "u@example.com"

    def test_second_mailbox_does_not_take_the_default(self, mb, fake_keyring):
        mb.save("a@firma.de", "a", "x")
        mb.save("b@firma.de", "b", "y")

        assert json.loads(fake_keyring.get_password(SERVICE, "accounts")) == ["a@firma.de", "b@firma.de"]
        assert fake_keyring.get_password(SERVICE, "default_account") == "a@firma.de"

    def test_empty_password_keeps_the_stored_one(self, mb, fake_keyring):
        mb.save("p1@firma.de", "p1", "x")
        mb.save("p1@firma.de", "p1b", "")

        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_username") == "p1b"
        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_password") == "x"

    def test_new_mailbox_without_password_is_refused(self, mb, fake_keyring):
        with pytest.raises(ValueError, match="Passwort ein"):
            mb.save("p1@firma.de", "p1", "")
        assert keys(fake_keyring) == set()

    @pytest.mark.parametrize("address", ["", "p1", " @ "])
    def test_address_must_be_an_address(self, mb, address):
        with pytest.raises(ValueError, match="E-Mail-Adresse"):
            mb.save_mailbox(address, "p1", "x")

    def test_username_is_required(self, mb):
        with pytest.raises(ValueError, match="Benutzernamen"):
            mb.save_mailbox("p1@firma.de", " ", "x")

    def test_panel_input_is_trimmed(self, mb, fake_keyring):
        mb.save_mailbox(" p1@firma.de ", " p1 ", "x ")

        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_username") == "p1"
        # Passwords may legitimately contain spaces.
        assert fake_keyring.get_password(SERVICE, "p1@firma.de:imap_password") == "x "


class TestRemove:
    def test_removing_the_default_moves_it_to_the_first_remaining(self, mb, fake_keyring):
        mb.save("a@firma.de", "a", "x")
        mb.save("b@firma.de", "b", "y")

        mb.remove("a@firma.de")

        assert json.loads(fake_keyring.get_password(SERVICE, "accounts")) == ["b@firma.de"]
        assert fake_keyring.get_password(SERVICE, "default_account") == "b@firma.de"
        assert not any(k.startswith("a@firma.de:") for k in keys(fake_keyring))

    def test_removing_the_last_clears_the_default(self, mb, fake_keyring):
        mb.save("a@firma.de", "a", "x")
        mb.remove("a@firma.de")

        assert keys(fake_keyring) == {"accounts"}
        assert json.loads(fake_keyring.get_password(SERVICE, "accounts")) == []

    def test_unknown_mailbox_is_refused(self, mb):
        with pytest.raises(ValueError, match="nicht mehr gespeichert"):
            mb.remove("x@firma.de")

    def test_remove_all_leaves_nothing(self, mb, fake_keyring):
        mb.save("a@firma.de", "a", "x")
        mb.save("work", "u", "y", server="mail.example.com", port="993")

        mb.remove_all()

        assert keys(fake_keyring) == set()


class TestList:
    def test_lists_names_usernames_and_default_never_passwords(self, mb):
        mb.save("a@firma.de", "a", "secret-a")
        mb.save("b@firma.de", "b", "secret-b")

        listed = mb.list_mailboxes()

        assert listed == [
            {"address": "a@firma.de", "username": "a", "default": True, "server": None},
            {"address": "b@firma.de", "username": "b", "default": False, "server": None},
        ]
        assert "secret" not in json.dumps(listed)


class TestServerFallback:
    """Panel mailboxes connect to the server set in the extension settings."""

    def test_account_without_server_uses_env(self, mb, monkeypatch):
        import imap_client

        monkeypatch.setenv("IMAP_SLIM_SERVER", "192.168.0.110")
        monkeypatch.setenv("IMAP_SLIM_PORT", "994")
        mb.save_mailbox("p1@firma.de", "p1", "x")

        assert imap_client.get_credentials("p1@firma.de") == ("192.168.0.110", "994", "p1", "x")

    def test_port_defaults_to_993(self, mb, monkeypatch):
        import imap_client

        monkeypatch.setenv("IMAP_SLIM_SERVER", "192.168.0.110")
        monkeypatch.delenv("IMAP_SLIM_PORT", raising=False)
        mb.save_mailbox("p1@firma.de", "p1", "x")

        assert imap_client.get_credentials("p1@firma.de")[1] == "993"

    def test_stored_server_wins_over_env(self, mb, monkeypatch):
        import imap_client

        monkeypatch.setenv("IMAP_SLIM_SERVER", "192.168.0.110")
        mb.save("work", "u", "x", server="mail.example.com", port="143")

        assert imap_client.get_credentials("work")[:2] == ("mail.example.com", "143")


class TestReviewFindings:
    def test_editing_keeps_a_custom_from(self, mb, fake_keyring):
        mb.save("me@x.de", "me", "x", server="mail.x.de", port="993", from_address="Max <me@x.de>")

        mb.save_mailbox("me@x.de", "me", "neu")

        assert fake_keyring.get_password(SERVICE, "me@x.de:from_address") == "Max <me@x.de>"

    def test_existing_terminal_account_without_address_name_is_editable(self, mb, fake_keyring):
        mb.save("work", "u", "x", server="mail.example.com", port="993")

        mb.save_mailbox("work", "u2", "")

        assert fake_keyring.get_password(SERVICE, "work:imap_username") == "u2"

    def test_list_shows_a_stored_server(self, mb):
        mb.save("work", "u", "x", server="mail.example.com", port="143")
        mb.save_mailbox("p1@firma.de", "p1", "x")

        servers = {m["address"]: m.get("server") for m in mb.list_mailboxes()}

        assert servers == {"work": "mail.example.com:143", "p1@firma.de": None}

    def test_missing_server_is_named_in_the_error(self, mb, monkeypatch):
        import imap_client

        monkeypatch.delenv("IMAP_SLIM_SERVER", raising=False)
        monkeypatch.delenv("IMAP_STREAM_SERVER", raising=False)
        mb.save_mailbox("p1@firma.de", "p1", "x")

        with pytest.raises(imap_client.IMAPError, match="no server"):
            imap_client.get_credentials("p1@firma.de")
