# Testing Guide

## Test Structure

Tests are organized in `tests/` directory by project type.

```
tests/imap-slim/
├── test_account_param.py
├── test_bodystructure.py
├── test_cache_validation.py
├── test_cli.py
├── test_debug_imap.py
├── test_drafts_replace.py
├── test_error_classify.py
├── test_failure_reporting.py
├── test_flag_parsing.py
├── test_html_quoting.py
├── test_imap_client.py
├── test_imap_stream_mcp.py
├── test_injection_defense.py
├── test_interleaved.py
├── test_layout.py
├── test_markdown.py
├── test_markdown_utils.py
├── test_quoting.py
├── test_reply_flow.py
├── test_search_criteria.py
├── test_search_flags.py
├── test_session.py
├── test_setup.py
└── test_tool_description.py
```

## Running Tests

```bash
# Run all tests
cd tests && uv run pytest

# Run one file
cd tests && uv run pytest imap-slim/test_search_criteria.py

# Common options
uv run pytest -v              # Verbose
uv run pytest -x              # Stop on first failure
uv run pytest -k "pattern"    # Run tests matching pattern
```

## Design Principles

**No External Dependencies**
- All file system, subprocess, and network operations are mocked
- Tests run offline in <100ms
- Deterministic, no flaky tests

**Stateless Fixtures**
- Each test gets clean state via pytest fixtures
- Tests can run in any order or in parallel
- Mock implementations in 'conftest.py'

**Comprehensive Coverage**
- Pure function tests (no I/O)
- Integration tests (mocked I/O)
- Edge cases: empty inputs, invalid data, missing fields
- Error paths: exceptions, command failures, cleanup
- Happy paths: complete workflows, various formats
