# IMAP Slim — Lightweight IMAP Email for LLM Agents

**Claude Code**: first enter `/plugin marketplace add maximizeschneider/imap-mcp` and then

- MCP server: `/plugin install imap-slim-mcp@flow-state`
- Skill + CLI: `/plugin install imap-slim-cli@flow-state`

**Other Agents**: tell the llm to install from `https://github.com/maximizeschneider/imap-mcp/imap-slim`

---

## Features

> **Secure and lightweight IMAP email CLI/MCP.**
> Reply as Drafts and send with your client. Delete restricted.

- 🪶 **~814 tokens** as an MCP server, or ~41 as a skill until you run a command
- 📧 **Read & search** — list, read, and search IMAP folders
- ✍️ **Write drafts** — `create` appends one, `replace` supersedes one; markdown renders to HTML
  plus a plain-text alternative, or send plain text exactly as written
- ↩️ **Replies** — the client quotes the original, HTML and inline images included, the way
  Thunderbird does; the model writes only the new text. Point-by-point for plain text
- 🔐 **Secure** — credentials in OS keychain (or env variables for Docker/CI)
- 🏢 **Multi-account** — multiple account support with named switching

Same actions are available as a skill-backed CLI (`imap-slim-cli`), which loads nothing into a
session until a command runs. Install either, or both.

[Full documentation →](imap-slim/README.md)

---

## Release Highlights

- **UPDATE** `imap-slim v2.1.0` — Replies: the client quotes the original, HTML and inline images
  included, with point-by-point replies for plain text. Available as a skill-backed CLI
  (`imap-slim-cli`) as well as the MCP server; `create`/`replace` named after what IMAP does.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) and [TESTING.md](TESTING.md).

## License

MIT. See [LICENSE](LICENSE).
