"""Environment-variable credentials must work where no keyring exists.

That is the documented Docker/CI setup, and the place a keyring backend is
least likely to be installed. keyring raised NoKeyringError before the env
fallback was ever reached.
"""

import imap_client
import pytest
from keyring.errors import KeyringLocked

ENV = {
    "IMAP_SLIM_SERVER": "imap.example.test",
    "IMAP_SLIM_PORT": "10993",
    "IMAP_SLIM_USERNAME": "me",
    "IMAP_SLIM_PASSWORD": "secret",
}


def _raise(exc):
    def get_password(service, key):
        raise exc

    return get_password


@pytest.fixture
def no_keyring(monkeypatch, fake_keyring):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(fake_keyring, "get_password", _raise(fake_keyring.errors.NoKeyringError("no backend")))


def test_credentials_come_from_env(no_keyring):
    assert imap_client.get_credentials() == ("imap.example.test", "10993", "me", "secret")


def test_no_accounts_and_no_default(no_keyring):
    assert imap_client.list_accounts() == []
    assert imap_client.get_default_account() is None


def test_a_locked_keyring_is_still_an_error(monkeypatch, fake_keyring):
    """Only a missing backend means "use env". A locked one holds real
    credentials, and silently switching to env would hide that."""
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(fake_keyring, "get_password", _raise(KeyringLocked("locked")))
    with pytest.raises(KeyringLocked):
        imap_client.get_credentials()


class TestFromAddressFromEnv:
    """With env-var config there was no From at all: drafts went out with an
    empty `From:` header."""

    def test_explicit_from(self, no_keyring, monkeypatch):
        monkeypatch.setenv("IMAP_SLIM_FROM", "Me <me@example.test>")
        assert imap_client.get_from_address() == "Me <me@example.test>"

    def test_a_login_that_is_an_address(self, no_keyring, monkeypatch):
        monkeypatch.setenv("IMAP_SLIM_USERNAME", "me@example.test")
        assert imap_client.get_from_address() == "me@example.test"

    def test_a_bare_login_is_the_last_resort(self, no_keyring):
        """Same rule as a keychain account."""
        assert imap_client.get_from_address() == "me"
