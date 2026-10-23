# Development

## Project-Level Development Setup

When developing this project, the MCP server points directly to local directories:

**MCP Server** ('.mcp.json'):
```json
{
  "mcpServers": {
    "imap-slim": {
      "command": "uv",
      "args": ["--directory", "./imap-slim", "run", "imap-slim"]
    }
  }
}
```

This setup ensures:
- Always using latest development version
- No reinstall needed after changes

Note: the plugin carries its own server config with `${CLAUDE_PLUGIN_ROOT}` for standalone installation. `imap-slim` names it `mcp-server.json`, deliberately not `.mcp.json`: a `.mcp.json` at a plugin root is auto-discovered and would start the server for the CLI install too.

## Dev Skills from flow-jigs

Builder and session skills live in [flow-jigs](https://github.com/vre/flow-jigs). Install via marketplace:
```bash
/plugin marketplace add vre/flow-jigs
/plugin install builder-skill@flow-jigs
```

Or symlink locally for development:
```bash
ln -s /path/to/flow-jigs/session-claude .claude/skills/session-claude
ln -s /path/to/flow-jigs/builder-skill .claude/skills/builder-skill
# etc.
```

Dev skill symlinks are gitignored — they won't push to the repo.

## Local Plugin Installation Behavior

### Files Are Referenced In Place

When installing marketplace from local directory (`/plugin marketplace add /xxx/flow-state`):

1. **Files referenced in place** - Claude reads directly from source directory
2. **No copying to `.claude` directory** - unlike GitHub plugins which are cloned to cache
3. **Changes are immediate** - edit files and they're live, no reinstall needed
4. **Perfect for development** - iterative workflow

## Development Workflow

### Local testing

```bash
/plugin marketplace add "$PWD"
/plugin install imap-slim-mcp@flow-state
```

### Validation

```bash
claude plugin validate .
```

### Iterative Development

1. Add local marketplace: `/plugin marketplace add /xxx/flow-state`
2. Install plugin: `/plugin install imap-slim-mcp@flow-state`
3. Edit sources or SKILL.md in `/xxx/flow-state/imap-slim/`
4. Changes are live (may need Claude reload)
5. Test, iterate, repeat

## Release Checklist

When releasing a plugin update from a worktree branch:

1. Update docs in root + affected plugin directory:
   - `README.md`
   - `DEVELOPMENT.md`
   - `TESTING.md`
   - `CHANGELOG.md` (where present)
2. Bump versions consistently:
   - `.claude-plugin/marketplace.json` (`metadata.version` and plugin `version`)
   - `<plugin>/pyproject.toml`
   - `<plugin>/CHANGELOG.md`
3. Rebase branch before merge:
   - `git pull --rebase origin main`
4. Validate after rebase:
   - run tests for affected plugin(s)
   - run lints/checks for changed files

## Environment traps

- **`tests/uv.lock` is not tracked** — `.gitignore` ignores every lockfile. A fresh worktree
  re-resolves and can pick different versions, so copy `tests/uv.lock` from main during worktree
  setup or the environment differs from the one the suite was green on.
- **`uv run --frozen` reuses the lock and never re-resolves.** It is the right flag for reproducing
  an environment and the wrong one for proving a packaging change: a broken `pyproject.toml` passed
  in a worktree and failed on main, where nothing was frozen.
- **Pin a dependency that renames its public API.** `mcp>=1.0.0` resolved to 2.x, which removed
  `mcp.server.fastmcp`, and the MCP plugin was dead on any fresh install while existing
  environments kept working. Unbounded upper ranges hide this until someone installs.
