# 0007 - Search terms map to RFC 3501 search keys only

## Context

The query language needed AND/OR/NOT, more fields and paging. Two shapes were possible: map
every term to a server-side SEARCH key, or fetch candidates and filter some terms client-side
(e.g. `has:attachment` from BODYSTRUCTURE).

## Decision

Every term is exactly one RFC 3501 search-key. Nothing is filtered client-side. No extension
(ESEARCH, SORT, X-GM-RAW) is required.

## Consequences

- Works unchanged on any IMAP4rev1 server; verified on Dovecot 2.3.
- Total counts are exact and paging is a slice of the UID list - cheap.
- OR and NOT compose in prefix form without parentheses.
- No `has:attachment`: IMAP has no key for it, and filtering client-side would make totals and
  paging cost a BODYSTRUCTURE fetch per candidate.
- Order is UID (arrival) order, not the Date header. SORT (RFC 5256) would fix that where the
  server supports it; not needed so far.
