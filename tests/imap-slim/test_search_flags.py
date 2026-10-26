"""Tests for flag-based search query parsing."""

import datetime
from unittest.mock import MagicMock, patch

import pytest
from search_query import parse_search_query


def parse_flag_query(query):
    """The flag criterion a query becomes on its own, or None if it is not a lone flag."""
    try:
        criteria = parse_search_query(query, datetime.date.today())
    except ValueError:
        return None
    return criteria[0] if len(criteria) == 1 else None


class TestParseFlagQuery:
    """Test flag query string -> IMAP criteria mapping."""

    # Positive flag queries
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("flagged", "FLAGGED"),
            ("flagged:yes", "FLAGGED"),
            ("is:flagged", "FLAGGED"),
            ("starred", "FLAGGED"),
            ("is:starred", "FLAGGED"),
        ],
    )
    def test_flagged_variants(self, query, expected):
        assert parse_flag_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("unflagged", "UNFLAGGED"),
            ("flagged:no", "UNFLAGGED"),
            ("is:unflagged", "UNFLAGGED"),
            ("unstarred", "UNFLAGGED"),
        ],
    )
    def test_unflagged_variants(self, query, expected):
        assert parse_flag_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("unread", "UNSEEN"),
            ("unseen", "UNSEEN"),
            ("seen:no", "UNSEEN"),
            ("is:unread", "UNSEEN"),
            ("is:unseen", "UNSEEN"),
        ],
    )
    def test_unread_variants(self, query, expected):
        assert parse_flag_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("read", "SEEN"),
            ("seen", "SEEN"),
            ("seen:yes", "SEEN"),
            ("is:read", "SEEN"),
            ("is:seen", "SEEN"),
        ],
    )
    def test_read_variants(self, query, expected):
        assert parse_flag_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("answered", "ANSWERED"),
            ("is:answered", "ANSWERED"),
            ("answered:yes", "ANSWERED"),
        ],
    )
    def test_answered_variants(self, query, expected):
        assert parse_flag_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("unanswered", "UNANSWERED"),
            ("is:unanswered", "UNANSWERED"),
            ("answered:no", "UNANSWERED"),
        ],
    )
    def test_unanswered_variants(self, query, expected):
        assert parse_flag_query(query) == expected

    @pytest.mark.parametrize(
        "query,expected",
        [
            ("deleted", "DELETED"),
            ("is:deleted", "DELETED"),
            ("deleted:yes", "DELETED"),
        ],
    )
    def test_deleted_variants(self, query, expected):
        assert parse_flag_query(query) == expected

    # Case insensitivity
    def test_case_insensitive(self):
        assert parse_flag_query("FLAGGED") == "FLAGGED"
        assert parse_flag_query("Is:Flagged") == "FLAGGED"
        assert parse_flag_query("UNREAD") == "UNSEEN"

    # Non-flag queries return None
    @pytest.mark.parametrize(
        "query",
        [
            "from:user@test.com",
            "subject:hello",
            "some random text",
            "since:2024-01-01",
            "",
        ],
    )
    def test_non_flag_returns_none(self, query):
        assert parse_flag_query(query) is None


class TestSearchMessagesFlagIntegration:
    """Test that search_messages() uses flag criteria."""

    @patch("session.get_session")
    def test_flagged_query_sends_correct_criteria(self, mock_get_session):
        from imap_client import search_messages

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.connection_ctx.return_value.__enter__.return_value = mock_client
        mock_session.connection_ctx.return_value.__exit__.return_value = False
        # search_messages is read-only, so it goes through run_op with retry=True.
        # A bare MagicMock would swallow the operation without running it.
        mock_session.run_op.side_effect = lambda operation, **kwargs: operation(mock_client)
        mock_get_session.return_value = mock_session
        mock_client.search.return_value = []

        search_messages("INBOX", "flagged")

        mock_client.search.assert_called_once_with(["FLAGGED"], charset=None)

    @patch("session.get_session")
    def test_is_unread_query_sends_unseen(self, mock_get_session):
        from imap_client import search_messages

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.connection_ctx.return_value.__enter__.return_value = mock_client
        mock_session.connection_ctx.return_value.__exit__.return_value = False
        # search_messages is read-only, so it goes through run_op with retry=True.
        # A bare MagicMock would swallow the operation without running it.
        mock_session.run_op.side_effect = lambda operation, **kwargs: operation(mock_client)
        mock_get_session.return_value = mock_session
        mock_client.search.return_value = []

        search_messages("INBOX", "is:unread")

        mock_client.search.assert_called_once_with(["UNSEEN"], charset=None)

    @patch("session.get_session")
    def test_non_flag_query_unchanged(self, mock_get_session):
        from imap_client import search_messages

        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.connection_ctx.return_value.__enter__.return_value = mock_client
        mock_session.connection_ctx.return_value.__exit__.return_value = False
        # search_messages is read-only, so it goes through run_op with retry=True.
        # A bare MagicMock would swallow the operation without running it.
        mock_session.run_op.side_effect = lambda operation, **kwargs: operation(mock_client)
        mock_get_session.return_value = mock_session
        mock_client.search.return_value = []

        search_messages("INBOX", "from:test@example.com")

        mock_client.search.assert_called_once_with(["FROM", "test@example.com"], charset=None)
