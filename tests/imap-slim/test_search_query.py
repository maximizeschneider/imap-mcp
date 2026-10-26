"""The search query language: what a typed query becomes on the wire.

Every term must come out as exactly one RFC 3501 search-key, so OR and NOT
compose in prefix form without parentheses.
"""

import datetime

import pytest
from imapclient.imapclient import _literal, _normalise_search_criteria
from search_query import parse_search_query

TODAY = datetime.date(2026, 10, 23)


def parse(query):
    return parse_search_query(query, TODAY)


def wire(query):
    """The bytes IMAPClient would send, joined - what the server parses."""
    return b" ".join(_normalise_search_criteria(parse(query), "UTF-8"))


class TestCombined:
    """Scenario: combined criteria."""

    def test_terms_are_anded(self):
        assert parse("from:boss unread since:2026-10-01") == ["FROM", "boss", "UNSEEN", "SINCE", datetime.date(2026, 10, 1)]

    def test_two_fields_no_longer_merge(self):
        """Used to send FROM "alice subject:invoice" and match nothing."""
        assert parse("from:alice subject:invoice") == ["FROM", "alice", "SUBJECT", "invoice"]

    def test_single_flag_word_keeps_its_meaning(self):
        assert parse("is:unread") == ["UNSEEN"]
        assert parse("flagged:no") == ["UNFLAGGED"]


class TestText:
    def test_bare_word_searches_subject_or_body(self):
        assert parse("invoice") == ["OR", "SUBJECT", "invoice", "BODY", "invoice"]

    def test_words_are_anded_separately(self):
        assert parse("project update") == ["OR", "SUBJECT", "project", "BODY", "project", "OR", "SUBJECT", "update", "BODY", "update"]

    def test_quoted_phrase_is_one_term(self):
        """Scenario: phrase."""
        assert parse('"quarterly report"') == ["OR", "SUBJECT", "quarterly report", "BODY", "quarterly report"]

    def test_quoted_flag_word_is_text(self):
        assert parse('"read"') == ["OR", "SUBJECT", "read", "BODY", "read"]

    def test_field_with_quoted_value(self):
        assert parse('from:"John Smith"') == ["FROM", "John Smith"]

    def test_unknown_prefix_is_text(self):
        assert parse("re:budget") == ["OR", "SUBJECT", "re:budget", "BODY", "re:budget"]

    def test_unterminated_quote_runs_to_end(self):
        assert parse('subject:"half open') == ["SUBJECT", "half open"]


class TestFields:
    @pytest.mark.parametrize(
        "query,key",
        [
            ("from:x", "FROM"),
            ("to:x", "TO"),
            ("cc:x", "CC"),
            ("bcc:x", "BCC"),
            ("subject:x", "SUBJECT"),
            ("body:x", "BODY"),
            ("text:x", "TEXT"),
        ],
    )
    def test_address_and_text_fields(self, query, key):
        assert parse(query) == [key, "x"]

    def test_field_name_is_case_insensitive_value_is_not(self):
        assert parse("FROM:Alice") == ["FROM", "Alice"]

    def test_on_date(self):
        assert parse("on:2026-10-01") == ["ON", datetime.date(2026, 10, 1)]

    def test_keyword_and_label(self):
        assert parse("keyword:$todo") == ["KEYWORD", "$todo"]
        assert parse("label:work") == ["KEYWORD", "work"]

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("larger:500", ["LARGER", 500]),
            ("larger:2k", ["LARGER", 2048]),
            ("smaller:5M", ["SMALLER", 5 * 1024 * 1024]),
            ("larger:10kb", ["LARGER", 10240]),
        ],
    )
    def test_sizes(self, query, expected):
        assert parse(query) == expected


class TestRelativeDates:
    """Scenario: relative date."""

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("newer_than:7d", ["SINCE", datetime.date(2026, 10, 16)]),
            ("newer_than:2w", ["SINCE", datetime.date(2026, 10, 9)]),
            ("newer_than:1m", ["SINCE", datetime.date(2026, 9, 23)]),
            ("older_than:1y", ["BEFORE", datetime.date(2025, 10, 23)]),
        ],
    )
    def test_units(self, query, expected):
        assert parse(query) == expected


class TestNegationAndOr:
    """Scenario: negation and OR."""

    def test_negated_field(self):
        assert parse("-subject:newsletter") == ["NOT", "SUBJECT", "newsletter"]

    def test_negated_flag(self):
        assert parse("-is:read") == ["NOT", "SEEN"]

    def test_negated_text(self):
        assert parse("-spam") == ["NOT", "OR", "SUBJECT", "spam", "BODY", "spam"]

    def test_or_between_two_terms(self):
        assert parse("from:alice OR from:bob -subject:newsletter") == [
            "OR", "FROM", "alice", "FROM", "bob", "NOT", "SUBJECT", "newsletter",
        ]  # fmt: skip

    def test_or_chains(self):
        assert parse("from:a OR from:b OR from:c") == ["OR", "OR", "FROM", "a", "FROM", "b", "FROM", "c"]

    def test_lowercase_or_is_a_word(self):
        assert parse("this or that")[:5] == ["OR", "SUBJECT", "this", "BODY", "this"]
        assert len(parse("this or that")) == 15

    @pytest.mark.parametrize("query", ["OR from:a", "from:a OR", "from:a OR OR from:b"])
    def test_dangling_or_is_reported(self, query):
        with pytest.raises(ValueError, match="OR needs a term on both sides"):
            parse(query)

    def test_lone_dash_is_text(self):
        assert parse("a - b")[5:10] == ["OR", "SUBJECT", "-", "BODY", "-"]


class TestBadValues:
    """AC3: a bad value names the expected form, nothing is guessed."""

    @pytest.mark.parametrize(
        "query,match",
        [
            ("since:yesterday", "YYYY-MM-DD"),
            ("on:2026-13-01", "YYYY-MM-DD"),
            ("newer_than:week", r"N\[dwmy\]"),
            ("larger:big", r"N\[k\|m\]"),
            ("from:", "needs a value"),
        ],
    )
    def test_reported(self, query, match):
        with pytest.raises(ValueError, match=match):
            parse(query)

    @pytest.mark.parametrize("query", ["", "   "])
    def test_empty_query(self, query):
        with pytest.raises(ValueError, match="empty"):
            parse(query)


class TestWireSafety:
    """AC4: IMAPClient quotes only on space, quote, backslash or empty. A value
    like (urgent) went out bare and the server parsed it as a list."""

    def test_atom_specials_go_as_a_literal(self):
        criteria = parse("subject:(urgent)")
        assert isinstance(criteria[1], _literal)
        assert bytes(criteria[1]) == b"(urgent)"

    @pytest.mark.parametrize("value", ["50%", "a*b", "x]", "{3}"])
    def test_other_specials(self, value):
        assert isinstance(parse(f"subject:{value}")[1], _literal)

    def test_plain_values_stay_strings(self):
        assert parse("subject:invoice") == ["SUBJECT", "invoice"]

    def test_wire_form_of_combined_query(self):
        assert wire("from:boss unread since:2026-10-01") == b"FROM boss UNSEEN SINCE 01-Oct-2026"

    def test_wire_form_of_phrase(self):
        assert wire('"quarterly report"') == b'OR SUBJECT "quarterly report" BODY "quarterly report"'
