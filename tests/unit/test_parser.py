"""Tests for log parsing."""

from ci_guardian.analysis.parser import parse_error_logs


def test_parse_pyright_errors():
    """Test parsing of pyright type errors."""
    logs = """
Running pyright...
src/main.py:10:5 - error: Argument of type "str" cannot be assigned to parameter "count" of type "int"
src/main.py:25:10 - error: Cannot access member "foo" for type "None"
Found 2 errors
"""
    result = parse_error_logs(logs)

    assert len(result.errors) == 2
    assert result.error_type == "pyright"
    assert result.errors[0].file_path == "src/main.py"
    assert result.errors[0].line_number == 10
    assert result.errors[0].column == 5
    assert "str" in result.errors[0].message


def test_parse_ruff_errors():
    """Test parsing of ruff lint errors."""
    logs = """
ruff check .
src/utils.py:15:1: I001 Import block is un-sorted or un-formatted
src/utils.py:42:80: E501 Line too long (120 > 100 characters)
Found 2 errors
"""
    result = parse_error_logs(logs)

    assert len(result.errors) == 2
    assert result.error_type == "ruff"
    assert result.errors[0].file_path == "src/utils.py"
    assert "Import block" in result.errors[0].message or "I001" in result.errors[0].message


def test_parse_pytest_failures():
    """Test parsing of pytest test failures."""
    logs = """
============================= FAILURES =============================
FAILED tests/test_api.py::test_create_user - AssertionError: assert 200 == 201
FAILED tests/test_api.py::test_delete_user - KeyError: 'user_id'
============================= short test summary info =====
"""
    result = parse_error_logs(logs)

    assert len(result.errors) >= 2
    assert result.error_type == "pytest"
    assert any("test_api.py" in e.file_path for e in result.errors if e.file_path)


def test_parse_typescript_errors():
    """Test parsing of TypeScript errors."""
    logs = """
src/App.tsx(15,10): error TS2322: Type 'string' is not assignable to type 'number'.
src/utils.ts(42,5): error TS2345: Argument of type 'undefined' is not assignable to parameter of type 'string'.
"""
    result = parse_error_logs(logs)

    assert len(result.errors) == 2
    assert result.error_type == "typescript"
    assert result.errors[0].file_path == "src/App.tsx"
    assert result.errors[0].line_number == 15


def test_parse_empty_logs():
    """Test parsing of logs with no errors."""
    logs = """
All checks passed!
✓ Lint passed
✓ Tests passed
✓ Build succeeded
"""
    result = parse_error_logs(logs)

    assert len(result.errors) == 0


def test_parse_generic_errors():
    """Test parsing of generic error patterns."""
    logs = """
Error: Cannot find module 'lodash'
fatal: not a git repository
npm ERR! code ENOENT
"""
    result = parse_error_logs(logs)

    # Should extract generic errors
    assert len(result.errors) >= 1


def test_affected_files_deduplication():
    """Test that affected_files returns unique file paths."""
    logs = """
src/main.py:10:5 - error: Type error 1
src/main.py:20:5 - error: Type error 2
src/utils.py:5:1 - error: Type error 3
"""
    result = parse_error_logs(logs)

    affected = result.affected_files
    assert len(affected) == 2
    assert "src/main.py" in affected
    assert "src/utils.py" in affected
