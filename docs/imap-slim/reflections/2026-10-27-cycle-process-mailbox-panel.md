# Process reflection: mailbox panel

- Framing changed direction three times in one session (form slots -> local web page -> MCP Apps). Each pivot came from HC asking a plain question ("where do I remove them?", "can MCP servers have UI?"). Keeping options open in the frame doc cost little; committing to slots early would have wasted a cycle.
- The spike paid for itself: it surfaced the two-process behaviour (model and panel calls do not share memory), which became the "keychain is the only state" constraint. No documentation mentions it.
- The spike could only be half-verified in the cloud container: a fake postMessage host proved the panel protocol, HC's Mac proved the host. Splitting checks that way and giving HC a numbered test script worked.
- A deployment fact (IMAP not reachable on the office server) surfaced only after the design was settled. Ask "does the client reach the server with the protocol we speak?" at the start of framing next time.
- No session-codex/sandvault in this environment: ORC implemented directly, review by an independent subagent instead of cross-model review.
