# Search query language, honest result counts, packaging fix

## Problem

- `search` accepts one criterion per query. `from:alice subject:invoice` becomes
  `FROM "alice subject:invoice"` and silently matches nothing.
- No `to:`, `cc:`, `body:`, `text:`, `on:`, relative dates, size, keyword; no negation, no OR,
  no quoted phrases.
- "Found 20" counts the rows returned after `limit`, not the matches. The model cannot tell 20
  matches from 2000 and has no way to page.
- list and search render the same message differently (sender with/without name, date format,
  empty subject) and duplicate ~40 lines of snippet fetching. The search copy swallows transport
  errors, so a connection dying mid-preview returns empty snippets instead of retrying.
- A value with atom-specials (`subject:(urgent)`) goes on the wire unquoted - IMAPClient quotes
  only on space, `"`, `\` or empty - and the server reads it as syntax.
- The wheel's `only-include` omits `quoting.py`; any non-editable install fails on import.

## Goal

One search call can express what a person would type into a mail client's search box, maps 1:1
to RFC 3501 SEARCH keys (server does all filtering, works on Dovecot without extensions), and
every list/search response says how many matched and how to get the next page.

## Design

Query grammar (pure function `parse_search_query(query, today) -> list`):

- Whitespace-separated terms, ANDed. `"..."` groups a phrase; `field:"..."` quotes a value.
- `-term` negates (`NOT key`). `a OR b` (uppercase `OR`) chains: `a OR b OR c`.
- Fields: `from: to: cc: bcc: subject: body: text:` → same-named IMAP keys.
  `since: before: on:` take YYYY-MM-DD. `newer_than:` / `older_than:` take `N[dwmy]`
  (m = 30 days, y = 365 days) → `SINCE` / `BEFORE` today minus N.
  `larger: smaller:` take `N[k|m]` bytes. `keyword:` / `label:` → `KEYWORD`.
- Flag words keep their current meaning (`unread`, `is:flagged`, `seen:no`, ...). Quote to search
  them as text: `"read"`.
- A bare word or phrase is `OR SUBJECT w BODY w`, as today. An unknown `x:y` is text, so
  `re:` and URLs still search.
- Output is flat prefix notation: every term is exactly one search-key, so `OR`/`NOT` need no
  parentheses.

Breaking: an unquoted multi-word value now splits - `from:John Smith` is `FROM John` AND
text `Smith`. Help text says to quote.

Paging: `offset` parameter (default 0) on list/search; results are a `MessagePage` (a list
with `.total`). Header: `Found 347 in INBOX, showing 1-20 (newest first). Next: offset 20`.

## Acceptance Criteria

- [x] AC1: Combined query → one AND-ed criteria list
- [x] AC2: Negation, OR, quoted phrases, every listed field, relative dates, sizes
- [x] AC3: Bad field values (date, size, duration) raise IMAPError naming the expected form
- [x] AC4: Values with atom-specials are sent as literals
- [x] AC5: list and search report total matches and accept offset; header shows range and next offset
- [x] AC6: list and search share one fetch/snippet/format path; search preview re-raises transport errors
- [x] AC7: Wheel contains every module the server imports

```gherkin
Scenario: combined criteria
  When I search INBOX for 'from:boss unread since:2026-10-01'
  Then the server receives FROM boss UNSEEN SINCE 1-Oct-2026

Scenario: negation and OR
  When I search for 'from:alice OR from:bob -subject:newsletter'
  Then the server receives OR FROM alice FROM bob NOT SUBJECT newsletter

Scenario: phrase
  When I search for '"quarterly report"'
  Then the server receives OR SUBJECT "quarterly report" BODY "quarterly report"

Scenario: relative date
  Given today is 2026-10-23
  When I search for 'newer_than:7d'
  Then the server receives SINCE 16-Oct-2026

Scenario: paging
  Given 347 messages match
  When I search with limit 20 offset 20
  Then I get matches 21-40 newest first
  And the header says "Found 347" and "Next: offset 40"

Scenario: last page
  When offset + limit >= total
  Then no "Next:" hint is shown
```

## Tasks

- [x] 1. Packaging: add `quoting.py` to `only-include`; test that every imported local module is listed
- [x] 2. `parse_search_query` + tests (AC1-AC4)
- [x] 3. Shared `fetch_summaries` used by list and search; one row renderer in actions (AC6)
- [x] 4. `offset` + `MessagePage.total` through session cache, imap_client, actions, CLI (AC5)
- [x] 5. Help text, tool description, SKILL.md, README, CHANGELOG, version 2.2.0
- [x] 6. Verify: full test suite, ruff, wheel contents
- [+] 7. Discovered: list stripped the flag backslash, so `\Seen` rendered as keyword `#Seen`. Fixed by the shared row path
- [+] 8. Discovered: `parse_flag_query` was dead after the parser; removed, its tests now go through `parse_search_query`
- [+] 9. Verified against Dovecot 2.3.21: 14 queries return the expected set; old code returned nothing for combined queries and a server error for `subject:(urgent)`

## Reflection

See `docs/imap-slim/reflections/2026-10-23-cycle-code-search-query-language.md`.
