"""Keychain account store: the one place that writes accounts.

setup.py (terminal) and the Desktop mailbox panel both write through here, so
the key layout read by imap_client.get_credentials has a single writer.
Messages are German because the panel shows them verbatim to its users.
"""

import json

import imap_client

ACCOUNT_KEYS = ("imap_server", "imap_port", "imap_username", "imap_password", "from_address")


def _set(key: str, value: str) -> None:
    imap_client.keyring.set_password(imap_client.SERVICE_NAME, key, value)


def _delete(key: str) -> None:
    try:
        imap_client.keyring.delete_password(imap_client.SERVICE_NAME, key)
    except imap_client.keyring.errors.PasswordDeleteError:
        pass


def _save_accounts(accounts: list[str]) -> None:
    _set("accounts", json.dumps(accounts))


def save(
    name: str,
    username: str,
    password: str | None,
    *,
    server: str | None = None,
    port: str | None = None,
    from_address: str | None = None,
) -> None:
    """Create or update an account.

    Args:
        name: Account name.
        username: IMAP login.
        password: Empty or None keeps the stored password of an existing account.
        server: None leaves it unset, so get_credentials falls back to IMAP_SLIM_SERVER.
        port: As server, with IMAP_SLIM_PORT.
        from_address: Address for From in drafts.

    Raises:
        ValueError: New account without a password.
    """
    accounts = imap_client.list_accounts()
    if not password and (name not in accounts or not imap_client._keyring_get(f"{name}:imap_password")):
        raise ValueError("Passwort fehlt.")

    if server:
        _set(f"{name}:imap_server", server)
    if port:
        _set(f"{name}:imap_port", port)
    _set(f"{name}:imap_username", username)
    if password:
        _set(f"{name}:imap_password", password)
    if from_address:
        _set(f"{name}:from_address", from_address)

    if name not in accounts:
        accounts.append(name)
        _save_accounts(accounts)
        if len(accounts) == 1:
            _set("default_account", name)


def save_mailbox(address: str, username: str, password: str) -> None:
    """Panel entry point: a new account is named by its address, which becomes its From.

    Editing an existing account keeps its From and accepts any name: the
    keychain is shared with setup.py, whose accounts may be named "work".
    """
    address, username = address.strip(), username.strip()
    exists = address in imap_client.list_accounts()
    local, _, domain = address.partition("@")
    if not exists and (not local or not domain):
        raise ValueError("Bitte eine gültige Mailadresse eingeben.")
    if not username:
        raise ValueError("Benutzername fehlt.")
    save(address, username, password, from_address=None if exists else address)


def remove(name: str) -> None:
    """Delete an account's keys; the default moves to the first remaining account.

    Raises:
        ValueError: Unknown account.
    """
    accounts = imap_client.list_accounts()
    if name not in accounts:
        raise ValueError(f"Postfach '{name}' nicht gefunden.")

    for suffix in ACCOUNT_KEYS:
        _delete(f"{name}:{suffix}")
    accounts.remove(name)
    _save_accounts(accounts)

    if imap_client._keyring_get("default_account") == name:
        if accounts:
            _set("default_account", accounts[0])
        else:
            _delete("default_account")


def remove_all() -> None:
    """Delete every account and the account list - uninstalling leaves the keychain untouched."""
    for name in imap_client.list_accounts():
        for suffix in ACCOUNT_KEYS:
            _delete(f"{name}:{suffix}")
    _delete("accounts")
    _delete("default_account")


def _stored_server(name: str) -> str | None:
    server = imap_client._keyring_get(f"{name}:imap_server")
    return f"{server}:{imap_client._keyring_get(f'{name}:imap_port') or '993'}" if server else None


def list_mailboxes() -> list[dict]:
    """Accounts with login, default marker and own server (None = extension setting). Never passwords."""
    default = imap_client.get_default_account()
    return [
        {
            "address": name,
            "username": imap_client._keyring_get(f"{name}:imap_username") or "",
            "default": name == default,
            "server": _stored_server(name),
        }
        for name in imap_client.list_accounts()
    ]
