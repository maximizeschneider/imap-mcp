"""AC5/AC6: list and search say how many matched, page through them, and
render a message the same way."""

import datetime
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from actions import MailAction, format_page_range, run_action
from imap_client import MessagePage, fetch_summaries, page_ids, search_messages
from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientAbortError
from session import AccountSession

TEXT_PART = (b"TEXT", b"PLAIN", (b"CHARSET", b"utf-8"), None, None, b"7BIT", 100, 5, None, None, None, None)


def _row(msg_id, flags=(b"\\Seen",)):
    envelope = SimpleNamespace(
        subject=f"Message {msg_id}".encode(),
        from_=[SimpleNamespace(name=b"Alice Example", mailbox=b"alice", host=b"example.com")],
        date=datetime.datetime(2026, 10, 23, 14, 2, 11),
    )
    return {b"ENVELOPE": envelope, b"FLAGS": list(flags), b"RFC822.SIZE": 10, b"BODYSTRUCTURE": TEXT_PART}


def _client(ids):
    client = MagicMock(spec=IMAPClient)
    client.select_folder.return_value = {b"UIDVALIDITY": 1, b"UIDNEXT": max(ids, default=0) + 1, b"EXISTS": len(ids)}
    client.search.return_value = list(ids)
    client.fetch.side_effect = lambda wanted, items: {i: _row(i) for i in wanted} if "ENVELOPE" in items else {}
    return client


def _search(client, query="from:alice", **kw):
    session = MagicMock()
    session.run_op.side_effect = lambda operation, **_: operation(client)
    with patch("session.get_session", return_value=session):
        return search_messages("INBOX", query, **kw)


class TestPageIds:
    @pytest.mark.parametrize(
        "limit,offset,expected",
        [(3, 0, [10, 9, 8]), (3, 3, [7, 6, 5]), (3, 8, [2, 1]), (3, 10, []), (3, 50, []), (20, 0, list(range(10, 0, -1)))],
    )
    def test_newest_first_slices(self, limit, offset, expected):
        assert page_ids(list(range(1, 11)), limit, offset) == expected


class TestSearchPaging:
    """Scenario: paging."""

    def test_second_page_and_total(self):
        client = _client(range(1, 348))

        page = _search(client, limit=20, offset=20)

        assert [m["id"] for m in page] == list(range(327, 307, -1))
        assert page.total == 347

    def test_unsorted_server_reply_still_pages_newest_first(self):
        client = _client([5, 1, 3])

        assert [m["id"] for m in _search(client, limit=2)] == [5, 3]

    def test_no_match_has_total_zero(self):
        page = _search(_client([]))
        assert page == [] and page.total == 0

    def test_query_error_names_the_help_topic(self):
        from imap_client import IMAPError

        with pytest.raises(IMAPError, match="help"):
            _search(_client([1]), query="since:yesterday")


class TestListPaging:
    def _session(self, client):
        session = AccountSession("test")
        session.connection = client
        session.last_activity = time.time()
        return session

    def test_total_is_the_folder_count(self):
        session = self._session(_client(range(1, 51)))

        page = session.get_messages("INBOX", limit=10)

        assert page.total == 50 and len(page) == 10

    def test_later_page_is_served_from_a_cached_first_page_that_covers_it(self):
        client = _client(range(1, 51))
        session = self._session(client)
        session.get_messages("INBOX", limit=20)
        client.search.reset_mock()

        page = session.get_messages("INBOX", limit=10, offset=10)

        client.search.assert_not_called()
        assert [m["id"] for m in page] == list(range(40, 30, -1))
        assert page.total == 50

    def test_page_beyond_the_cache_is_fetched_and_not_cached(self):
        client = _client(range(1, 51))
        session = self._session(client)
        session.get_messages("INBOX", limit=10)

        page = session.get_messages("INBOX", limit=10, offset=30)

        assert [m["id"] for m in page] == list(range(20, 10, -1))
        assert session.message_cache["INBOX"].limit == 10
        assert session.message_cache["INBOX"].messages[0]["id"] == 50


class TestOneRowShape:
    """AC6: list and search used to disagree on sender, date, subject and flags."""

    def test_row_fields(self):
        (row,) = fetch_summaries(_client([7]), [7], preview=False)

        assert row["from"] == "Alice Example <alice@example.com>"
        assert row["date"] == "2026-10-23 14:02"
        assert row["flags"] == ["\\Seen"]

    def test_missing_subject(self):
        client = _client([7])
        row = _row(7)
        row[b"ENVELOPE"].subject = None
        client.fetch.side_effect = lambda wanted, items: {7: row}

        assert fetch_summaries(client, [7], preview=False)[0]["subject"] == "(no subject)"

    def test_list_renders_seen_as_a_flag_not_a_keyword(self):
        """List stripped the backslash, so format_flags showed \\Seen as #Seen."""
        session = AccountSession("test")
        session.connection = _client([1])
        session.last_activity = time.time()
        with patch("session.get_session", return_value=session):
            out = run_action(MailAction(action="list", folder="INBOX", preview=False))

        assert "[seen]" in out
        assert "#Seen" not in out


class TestPreviewTransportFailure:
    """A connection dying mid-preview must reach the retry, not become empty snippets."""

    def test_search_preview_reraises(self):
        client = _client([1])

        def fetch(wanted, items):
            if "ENVELOPE" in items:
                return {i: _row(i) for i in wanted}
            raise IMAPClientAbortError("socket error: EOF")

        client.fetch.side_effect = fetch

        with pytest.raises(IMAPClientAbortError):
            _search(client, preview=True)

    def test_a_refused_section_costs_only_the_snippet(self):
        client = _client([1])

        def fetch(wanted, items):
            if "ENVELOPE" in items:
                return {i: _row(i) for i in wanted}
            raise ValueError("BAD section")

        client.fetch.side_effect = fetch

        page = _search(client, preview=True)
        assert page[0]["snippet"] == ""


class TestHeader:
    """Scenario: paging / last page."""

    def test_more_to_come(self):
        assert format_page_range(347, 20, 20) == "showing 21-40 (newest first). Next: offset 40"

    def test_last_page(self):
        assert format_page_range(25, 20, 5) == "showing 21-25 (newest first)"

    def test_search_output(self):
        with patch("actions.search_messages", return_value=MessagePage([fetch_summaries(_client([9]), [9], False)[0]], total=347)):
            out = run_action(MailAction(action="search", folder="INBOX", payload="from:alice", preview=False, limit=1))

        assert "Found 347 in INBOX, showing 1-1 (newest first). Next: offset 1" in out

    def test_offset_past_the_end(self):
        with patch("actions.search_messages", return_value=MessagePage([], total=12)):
            out = run_action(MailAction(action="search", folder="INBOX", payload="x", preview=False, offset=40))

        assert "No messages at offset 40 - 12 match" in out

    def test_list_output(self):
        with patch("actions.list_messages", return_value=MessagePage(fetch_summaries(_client([3, 2]), [3, 2], False), total=2)):
            out = run_action(MailAction(action="list", folder="INBOX", preview=False))

        assert "2 messages, showing 1-2 (newest first)" in out
        assert "Next" not in out


class TestCountWording:
    def test_one_message(self):
        with patch("actions.list_messages", return_value=MessagePage(fetch_summaries(_client([3]), [3], False), total=1)):
            out = run_action(MailAction(action="list", folder="INBOX", preview=False))

        assert "1 message, showing 1-1" in out
