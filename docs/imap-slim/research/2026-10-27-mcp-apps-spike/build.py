"""Inline the ext-apps bundle into panel.html - the default MCP Apps CSP allows
inline scripts only, no external script sources."""

import re
from pathlib import Path

here = Path(__file__).parent
bundle = (here / "../../../../imap-slim/vendor/ext-apps-2.0.4-app-with-deps.js").read_text(encoding="utf-8")

# The bundle is an ES module ending in one export list; expose it as a global instead.
m = re.search(r"export\{([^}]*)\};?\s*$", bundle)
pairs = [p.split(" as ") for p in m.group(1).split(",")]
glue = "window.McpApps={" + ",".join(f"{alias}:{local}" for local, alias in pairs) + "};"
bundle = bundle[: m.start()] + glue

assert "</script" not in bundle
src = (here / "panel.src.html").read_text(encoding="utf-8")
(here / "panel.html").write_text(src.replace("/*__BUNDLE__*/", bundle), encoding="utf-8")
print(f"panel.html: {len(src) + len(bundle)} chars")
