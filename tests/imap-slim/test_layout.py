"""AC2/AC5: the rename must not break an existing install, and render.py must
hold the shared helpers rather than a copy of them.

These guard repo structure rather than behaviour, which is unusual in a plugin
test suite. They earn their place because the compatibility symlink is the only
reason an already-installed plugin keeps working after the directory was renamed
- deleting it would break the user's mail tool with nothing failing in CI.
"""

import json
from pathlib import Path

import render
import tomllib

REPO = Path(__file__).resolve().parent.parent.parent


class TestOldPathsStillResolve:
    def test_package_directory_is_imap_slim(self):
        assert (REPO / "imap-slim" / "imap_stream_mcp.py").is_file()

    def test_the_previous_names_are_symlinks_to_it(self):
        for legacy in ("imap-slim-mcp", "imap-stream-mcp"):
            link = REPO / legacy
            assert link.is_symlink(), f"{legacy} must stay a symlink so installed plugins keep working"
            assert link.readlink().name == "imap-slim", f"{legacy} must point at imap-slim, not at another symlink"

    def test_a_file_opens_through_each_legacy_path(self):
        canonical = (REPO / "imap-slim" / "pyproject.toml").read_text()
        for legacy in ("imap-slim-mcp", "imap-stream-mcp"):
            assert (REPO / legacy / "pyproject.toml").read_text() == canonical

    def test_marketplace_points_at_the_real_directory(self):
        import json

        marketplace = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
        entry = next(p for p in marketplace["plugins"] if p["name"] == "imap-slim-mcp")
        assert entry["source"] == "./imap-slim"


class TestRenderHoldsTheSharedHelpers:
    """POTENTIAL_INJECTION_NOTICE is deliberately absent: nothing in imap-slim
    referenced it, before this cut or after. It was dead in imap_stream_mcp.py
    and was not carried into a new module. youtube-to-markdown has its own
    same-named constant, which is unrelated."""

    SHARED = (
        "format_flags",
        "format_attachment_line",
        "format_description",
        "classify_connection_error",
        "POTENTIAL_INJECTION_WARNING",
    )

    def test_render_defines_them(self):
        for name in self.SHARED:
            assert hasattr(render, name), f"render.{name} missing"

    def test_the_action_layer_imports_rather_than_redefines(self):
        """Cut 4a moved the dispatcher into actions.py, so that is what uses the
        shared helpers now; imap_stream_mcp is only the FastMCP wrapper."""
        import actions

        for name in self.SHARED:
            assert getattr(actions, name) is getattr(render, name), f"{name} is a copy, not the shared one"


class TestDesktopExtensionManifest:
    """manifest.json is packed into the .mcpb; nothing else reads it, so drift
    would only show after a user installed a mislabelled extension."""

    def test_version_matches_the_package(self):
        manifest = json.loads((REPO / "imap-slim" / "manifest.json").read_text())
        pyproject = tomllib.loads((REPO / "imap-slim" / "pyproject.toml").read_text())
        assert manifest["version"] == pyproject["project"]["version"]

    def test_every_form_field_reaches_the_server(self):
        manifest = json.loads((REPO / "imap-slim" / "manifest.json").read_text())
        env = " ".join(manifest["server"]["mcp_config"]["env"].values())
        for key, option in manifest["user_config"].items():
            assert f"${{user_config.{key}}}" in env
            # An unset optional field without a default is passed through as the literal placeholder.
            assert option.get("required") or "default" in option, key


class TestWheelCarriesEveryModule:
    """only-include lists modules by hand; quoting.py was missing from it, so a
    non-editable install (uvx, pip) failed on `import actions`."""

    def test_every_local_import_is_packaged(self):
        import ast

        import tomllib

        pkg = REPO / "imap-slim"
        config = tomllib.loads((pkg / "pyproject.toml").read_text())
        packaged = set(config["tool"]["hatch"]["build"]["targets"]["wheel"]["only-include"])
        local = {p.stem for p in pkg.glob("*.py")}

        needed = set()
        for name in packaged:
            for node in ast.walk(ast.parse((pkg / name).read_text())):
                if isinstance(node, ast.Import):
                    needed.update(a.name.split(".")[0] for a in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    needed.add(node.module.split(".")[0])

        missing = {f"{m}.py" for m in needed & local} - packaged
        assert not missing, f"imported but not in only-include: {sorted(missing)}"
