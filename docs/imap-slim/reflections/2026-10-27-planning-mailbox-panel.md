# Planning reflection: mailbox panel

- Storing no server per panel account was decided in planning, not framing: the open IMAP blocker means the address may change, and re-adding every mailbox for that would be the wrong cost.
- Registering app-only tools behind an env flag closes the gap the spec leaves: hosts without MCP Apps list every tool to the model. The flag is set only by the .mcpb.
- In-panel two-step confirmation instead of confirm(): the sandboxed iframe has no allow-modals. Found by reading the sandbox model, not by testing on Desktop.
- Inlining the bridge at resource-read time avoids a build step and a generated 0.5 MB file in git.
