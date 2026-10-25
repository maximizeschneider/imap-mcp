# Manual test mailbox for imap-slim

A throwaway IMAP server with mock mail, a webmail to look at it, and a script that calls every
`use_mail` action. Never point these scripts at a real mailbox: they create drafts and change flags.

## Windows setup (once)

```powershell
winget install FiloSottile.mkcert Docker.DockerDesktop
mkcert -install                       # trusts a local CA for your Windows user
cd tests\imap-slim\manual
mkdir certs; cd certs
mkcert -pkcs12 -p12-file localhost.p12 localhost 127.0.0.1   # password is "changeit"
cd ..
```

imap-slim always uses TLS and verifies the certificate. `mkcert -install` puts its CA in the
Windows certificate store, which Python reads, so no code or setting is needed for the test.

## Run

```powershell
docker compose up -d        # starts the server and seeds it: 8 INBOX messages, folders, one draft
```

- Webmail: <http://localhost:8000>, user `anna`, password `secret`
- GreenMail keeps mail in memory. Reset: `docker compose restart greenmail; docker compose up seed`

## Test

Scripted, all actions in ~20 s (needs `uv`: `winget install astral-sh.uv`; it fetches Python itself):

```powershell
uv run --no-project smoke_mcp.py                         # server from this repo
uv run --no-project smoke_mcp.py --server-dir <unpacked .mcpb>  # the bundle exactly as shipped
```

By hand in Claude Desktop: install the `.mcpb`, fill in server `localhost`, port `3993`,
username `anna`, password `secret`, From `anna@localhost`. Then ask Claude for each action:
list and search INBOX, read the HTML mail (logo), save the invoice attachment, flag a message,
draft a reply to Ville's meeting mail, replace that draft. Check the results in webmail.

## What the seed covers

Plain and HTML mail, an inline image, PDF/PNG/CSV attachments, a forwarded message, a thread,
a prompt-injection mail, Finnish text and emoji, `Reply-To`, read/unread/flagged, nested folders
and an existing draft.
