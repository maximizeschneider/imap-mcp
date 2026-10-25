"""Drive every use_mail action through the MCP server over stdio, as Claude would.

Run against the mailbox from seed_mailbox.py, never a real one: it creates drafts
and changes flags. Prints each response head and exits non-zero on any error.

    python smoke_mcp.py                       # server from this repo via uv
    python smoke_mcp.py --server-dir <dir>    # e.g. an unpacked .mcpb
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_PKG = Path(__file__).resolve().parents[3] / "imap-slim"


class Server:
    def __init__(self, cmd: list[str], env: dict[str, str]):
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=env, text=True, encoding="utf-8")
        self.next_id = 0
        self.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}})
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def send(self, msg: dict) -> None:
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, params: dict) -> dict:
        self.next_id += 1
        self.send({"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params})
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise SystemExit("server exited - run it by hand to see its stderr")
            msg = json.loads(line)
            if msg.get("id") == self.next_id:
                return msg

    def call(self, **params) -> tuple[str, bool]:
        msg = self.request("tools/call", {"name": "use_mail", "arguments": {"params": params}})
        if "error" in msg:
            return json.dumps(msg["error"]), True
        result = msg["result"]
        text = "\n".join(c.get("text", "") for c in result.get("content", []))
        return text, bool(result.get("isError")) or text.startswith("Error")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server-dir", default=str(REPO_PKG))
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", default="3993")
    ap.add_argument("--user", default="anna")
    ap.add_argument("--password", default="secret")
    ap.add_argument("--from-address", default="anna@localhost")
    ap.add_argument("--chars", type=int, default=300, help="response characters to print")
    a = ap.parse_args()

    env = {k: v for k, v in os.environ.items() if not k.startswith(("IMAP_SLIM_", "IMAP_STREAM_"))}
    env |= {
        "IMAP_SLIM_SERVER": a.host,
        "IMAP_SLIM_PORT": a.port,
        "IMAP_SLIM_USERNAME": a.user,
        "IMAP_SLIM_PASSWORD": a.password,
        "IMAP_SLIM_FROM": a.from_address,
    }
    srv = Server(["uv", "run", "--directory", a.server_dir, "imap_stream_mcp.py"], env)

    tools = srv.request("tools/list", {})["result"]["tools"]
    print("tools:", [t["name"] for t in tools])

    attachment = Path(tempfile.gettempdir()) / "smoke-note.txt"
    attachment.write_text("attached by smoke_mcp.py", encoding="utf-8")

    failures = []

    def step(label: str, expect_error: bool = False, **params) -> str:
        text, is_error = srv.call(**params)
        ok = is_error == expect_error
        print(f"\n=== {'PASS' if ok else 'FAIL'} {label}\n{text[: a.chars]}")
        if not ok:
            failures.append(label)
        return text

    step("accounts", action="accounts")
    step("folders", action="folders")
    step("help", action="help")
    step("list INBOX", action="list", folder="INBOX", preview=True)
    step("list nested folder", action="list", folder="Work/Projects", preview=False)
    step("search sender", action="search", folder="INBOX", payload="from:mikko@example.com", preview=True)
    step("search text (non-ASCII)", action="search", folder="INBOX", payload="budjetti", preview=False)
    step("read plain", action="read", folder="INBOX", payload="2")
    step("read full", action="read", folder="INBOX", payload="3:full")
    step("read HTML + inline image", action="read", folder="INBOX", payload="4")
    step("read with attachments", action="read", folder="INBOX", payload="5")
    step("read forwarded message", action="read", folder="INBOX", payload="6")
    injection = step("read prompt injection", action="read", folder="INBOX", payload="7")
    if "EXTERNAL_EMAIL" not in injection:
        failures.append("injection not wrapped as untrusted")
    step("read as quote block", action="read", folder="INBOX", payload="3:quote")
    step("download attachment", action="attachment", folder="INBOX", payload="5:0")
    step("cleanup attachments", action="cleanup")
    step("flag", action="flag", folder="INBOX", payload="1:+Flagged,-Seen")

    created = step(
        "create markdown draft with attachment",
        action="create",
        format="markdown",
        payload=json.dumps(
            {
                "to": "boss@example.com",
                "subject": "Smoke test",
                "body": "**Bold**, a list:\n\n- one\n- two",
                "attachments": [str(attachment)],
            }
        ),
    )
    step("create plain reply (quote)", action="create", format="plain", quote="INBOX:8", payload=json.dumps({"body": "Tiistai sopii."}))
    step("create HTML reply (quote)", action="create", format="markdown", quote="INBOX:4", payload=json.dumps({"body": "Looks good!"}))

    draft_id = re.search(r"\b(?:id|ID|Id)\D{0,5}(\d+)", created)
    if draft_id:
        step(
            "replace draft",
            action="replace",
            folder="Drafts",
            format="markdown",
            payload=json.dumps({"id": int(draft_id.group(1)), "body": "Replaced body."}),
        )
    else:
        failures.append("no draft id in create response")
    step("list Drafts", action="list", folder="Drafts", preview=True)
    step("bad folder is an error", expect_error=True, action="list", folder="NoSuchFolder", preview=False)

    srv.proc.stdin.close()
    srv.proc.wait(timeout=10)
    attachment.unlink(missing_ok=True)
    print(f"\n{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
