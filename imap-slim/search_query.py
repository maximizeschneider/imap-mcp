"""Turn a typed search query into RFC 3501 SEARCH criteria.

Terms are ANDed; `-term` negates, `a OR b` alternates, `"..."` groups a phrase.
Each term becomes exactly one search-key, so OR and NOT compose in prefix form
and no parentheses are ever needed. Every key is plain RFC 3501, so the server
does all the filtering and no extension is required.
"""

import datetime
import re

from imapclient.imapclient import _literal

# Flag query -> IMAP search criterion mapping
# Liberal parsing: "flagged", "flagged:yes", "is:flagged", "starred" all work
FLAG_QUERY_MAP: dict[str, str] = {
    # Flagged/starred
    "flagged": "FLAGGED",
    "flagged:yes": "FLAGGED",
    "is:flagged": "FLAGGED",
    "starred": "FLAGGED",
    "is:starred": "FLAGGED",
    "unflagged": "UNFLAGGED",
    "flagged:no": "UNFLAGGED",
    "is:unflagged": "UNFLAGGED",
    "unstarred": "UNFLAGGED",
    # Seen/read
    "seen": "SEEN",
    "seen:yes": "SEEN",
    "read": "SEEN",
    "is:seen": "SEEN",
    "is:read": "SEEN",
    "unseen": "UNSEEN",
    "seen:no": "UNSEEN",
    "unread": "UNSEEN",
    "is:unseen": "UNSEEN",
    "is:unread": "UNSEEN",
    # Answered
    "answered": "ANSWERED",
    "answered:yes": "ANSWERED",
    "is:answered": "ANSWERED",
    "unanswered": "UNANSWERED",
    "answered:no": "UNANSWERED",
    "is:unanswered": "UNANSWERED",
    # Deleted
    "deleted": "DELETED",
    "deleted:yes": "DELETED",
    "is:deleted": "DELETED",
}

_TEXT_FIELDS = {
    "from": "FROM",
    "to": "TO",
    "cc": "CC",
    "bcc": "BCC",
    "subject": "SUBJECT",
    "body": "BODY",
    "text": "TEXT",
}
_DATE_FIELDS = {"since": "SINCE", "before": "BEFORE", "on": "ON"}
_RELATIVE_FIELDS = {"newer_than": "SINCE", "older_than": "BEFORE"}
_SIZE_FIELDS = {"larger": "LARGER", "smaller": "SMALLER"}
_KEYWORD_FIELDS = {"keyword", "label"}
_FIELDS = _TEXT_FIELDS.keys() | _DATE_FIELDS.keys() | _RELATIVE_FIELDS.keys() | _SIZE_FIELDS.keys() | _KEYWORD_FIELDS

_DAYS_PER_UNIT = {"d": 1, "w": 7, "m": 30, "y": 365}
_BYTES_PER_UNIT = {"": 1, "k": 1024, "kb": 1024, "m": 1024**2, "mb": 1024**2}

# IMAPClient quotes a value only for space, quote, backslash or empty. Any other
# atom-special left bare is read by the server as syntax: (urgent) is a list.
_ATOM_SPECIALS = re.compile(r"[(){%*\]\x00-\x1f\x7f]")


def _wire_value(value: str) -> str | bytes:
    if value.isascii() and _ATOM_SPECIALS.search(value):
        return _literal(value.encode("ascii"))
    return value


def _tokens(query: str):
    """Yield (negated, text, quoted) per whitespace-separated term.

    `quoted` is True when the whole term was a quoted phrase; `field:"a b"`
    yields its text with the quotes removed and quoted=False, since it still
    names a field.
    """
    i, n = 0, len(query)
    while i < n:
        if query[i].isspace():
            i += 1
            continue
        negated = query[i] == "-" and i + 1 < n and not query[i + 1].isspace()
        if negated:
            i += 1
        if query[i] == '"':
            end = query.find('"', i + 1)
            end = n if end == -1 else end
            yield negated, query[i + 1 : end], True
            i = end + 1
            continue
        start = i
        while i < n and not query[i].isspace():
            if query[i] == ":" and i + 1 < n and query[i + 1] == '"':
                end = query.find('"', i + 2)
                end = n if end == -1 else end
                yield negated, query[start:i] + ":" + query[i + 2 : end], False
                i = end + 1
                break
            i += 1
        else:
            yield negated, query[start:i], False


def _parse_date(value: str, field: str) -> datetime.date:
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{field}:' needs a date as YYYY-MM-DD, got '{value}'") from None


def _parse_age(value: str, field: str, today: datetime.date) -> datetime.date:
    m = re.fullmatch(r"(\d+)([dwmy])", value.lower())
    if not m:
        raise ValueError(f"'{field}:' needs N[dwmy] (days, weeks, 30-day months, 365-day years), got '{value}'")
    return today - datetime.timedelta(days=int(m[1]) * _DAYS_PER_UNIT[m[2]])


def _parse_size(value: str, field: str) -> int:
    m = re.fullmatch(r"(\d+)(|k|kb|m|mb)", value.lower())
    if not m:
        raise ValueError(f"'{field}:' needs a size as N[k|m] bytes, got '{value}'")
    return int(m[1]) * _BYTES_PER_UNIT[m[2]]


def _term(text: str, quoted: bool, today: datetime.date) -> list:
    """One term as one search-key."""
    if not quoted:
        flag = FLAG_QUERY_MAP.get(text.lower())
        if flag:
            return [flag]
        field, sep, value = text.partition(":")
        field = field.lower()
        if sep and field in _FIELDS:
            if not value:
                raise ValueError(f"'{field}:' needs a value")
            if field in _TEXT_FIELDS:
                return [_TEXT_FIELDS[field], _wire_value(value)]
            if field in _DATE_FIELDS:
                return [_DATE_FIELDS[field], _parse_date(value, field)]
            if field in _RELATIVE_FIELDS:
                return [_RELATIVE_FIELDS[field], _parse_age(value, field, today)]
            if field in _SIZE_FIELDS:
                return [_SIZE_FIELDS[field], _parse_size(value, field)]
            return ["KEYWORD", _wire_value(value)]
    value = _wire_value(text)
    return ["OR", "SUBJECT", value, "BODY", value]


def parse_search_query(query: str, today: datetime.date) -> list:
    """Parse a search query into flat IMAPClient criteria.

    Args:
        query: e.g. 'from:boss unread newer_than:7d -subject:newsletter'
        today: Anchor for newer_than/older_than.

    Returns:
        Criteria list for IMAPClient.search.

    Raises:
        ValueError: Empty query, dangling OR, or a field value in the wrong form.
    """
    terms: list[list] = []
    pending_or = False
    for negated, text, quoted in _tokens(query):
        if text == "OR" and not quoted and not negated:
            if not terms or pending_or:
                raise ValueError("OR needs a term on both sides")
            pending_or = True
            continue
        term = _term(text, quoted, today)
        if negated:
            term = ["NOT", *term]
        if pending_or:
            terms[-1] = ["OR", *terms[-1], *term]
            pending_or = False
        else:
            terms.append(term)
    if pending_or:
        raise ValueError("OR needs a term on both sides")
    if not terms:
        raise ValueError("Search query is empty")
    return [item for term in terms for item in term]
