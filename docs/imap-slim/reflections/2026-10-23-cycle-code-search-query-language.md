# Cycle: search query language, paging, packaging fix

## What went well

- The parser is a pure function with a `today` argument; 70 tests run in milliseconds and pin
  the exact criteria list. Testing the wire bytes via IMAPClient's own normaliser caught nothing
  new but makes the "one search-key per term" claim checkable.
- A throwaway Dovecot in the container (plain IMAP on a high port, static passdb) gave a real
  server in under two minutes. It confirmed the literal path for atom-specials and UTF-8 search,
  and reproduced both old bugs. Worth repeating for any wire-level change.

## What changed from plan

- Two extra bugs found while unifying list and search: list rendered `\Seen` as `#Seen`, and the
  cache flag update stored the stripped form. The shared row path fixed both.
- The tool description budget rose by 110 chars for `offset` and one combined example.

## Lessons

- Duplicated code had drifted in three ways (flag form, transport handling, sender format).
  None was caught by tests because each copy had its own mocks.
- `Mock(name=...)` sets the mock's name, not an attribute; test fixtures for envelope addresses
  should use SimpleNamespace.
- Process deviation: paging/row tests were written after the code, not before. Both bug tests
  were then run against the old code to prove they would have failed.
- No cross-model review ran: the `session-codex` skill is not available in this cloud session.
