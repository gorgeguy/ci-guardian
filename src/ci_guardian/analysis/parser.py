"""Log parsing for error extraction."""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedError:
    """A single parsed error from CI logs."""

    error_type: str  # e.g., "type_error", "lint", "test_failure"
    message: str
    file_path: str | None = None
    line_number: int | None = None
    column: int | None = None
    context: str = ""  # Additional context around the error


@dataclass
class ParsedErrors:
    """Collection of parsed errors from CI logs."""

    errors: list[ParsedError] = field(default_factory=list)
    raw_logs: str = ""
    error_type: str = "unknown"  # Overall error type

    @property
    def affected_files(self) -> list[str]:
        """Get unique list of affected files."""
        return list({e.file_path for e in self.errors if e.file_path})


# Regex patterns for different error types
PATTERNS = {
    "pyright": [
        # Standard pyright error: file.py:10:5 - error: message
        re.compile(
            r"^(?P<file>[^\s:]+\.py):(?P<line>\d+):(?P<col>\d+)\s*[-–]\s*error:\s*(?P<msg>.+)$",
            re.MULTILINE,
        ),
    ],
    "mypy": [
        # mypy error: file.py:10: error: message
        re.compile(
            r"^(?P<file>[^\s:]+\.py):(?P<line>\d+):\s*error:\s*(?P<msg>.+)$",
            re.MULTILINE,
        ),
    ],
    "ruff": [
        # ruff error: file.py:10:5: E501 message
        re.compile(
            r"^(?P<file>[^\s:]+\.py):(?P<line>\d+):(?P<col>\d+):\s*(?P<code>[A-Z]\d+)\s*(?P<msg>.+)$",
            re.MULTILINE,
        ),
    ],
    "eslint": [
        # ESLint: /path/file.ts:10:5 error message
        re.compile(
            r"^\s*(?P<file>[^\s:]+\.[jt]sx?):(?P<line>\d+):(?P<col>\d+)\s+(?:error|warning)\s+(?P<msg>.+)$",
            re.MULTILINE,
        ),
    ],
    "typescript": [
        # TypeScript: file.ts(10,5): error TS1234: message
        re.compile(
            r"^(?P<file>[^\s(]+\.[jt]sx?)\((?P<line>\d+),(?P<col>\d+)\):\s*error\s+(?P<code>TS\d+):\s*(?P<msg>.+)$",
            re.MULTILINE,
        ),
    ],
    "pytest": [
        # pytest FAILED tests/test_foo.py::test_bar
        re.compile(
            r"^FAILED\s+(?P<file>[^\s:]+\.py)::(?P<test>\w+)",
            re.MULTILINE,
        ),
        # pytest AssertionError
        re.compile(
            r"^(?P<file>[^\s:]+\.py):(?P<line>\d+):\s*(?:AssertionError|assert\s)",
            re.MULTILINE,
        ),
    ],
    "jest": [
        # Jest: FAIL src/foo.test.ts
        re.compile(
            r"^FAIL\s+(?P<file>[^\s]+\.(?:test|spec)\.[jt]sx?)$",
            re.MULTILINE,
        ),
    ],
}


def parse_error_logs(logs: str) -> ParsedErrors:
    """
    Parse CI logs to extract structured error information.

    Args:
        logs: Raw CI log output

    Returns:
        ParsedErrors containing extracted error details
    """
    errors: list[ParsedError] = []
    detected_type = "unknown"

    # Try each error type pattern
    for error_type, patterns in PATTERNS.items():
        for pattern in patterns:
            matches = pattern.finditer(logs)
            for match in matches:
                groups = match.groupdict()

                error = ParsedError(
                    error_type=error_type,
                    message=groups.get("msg", "") or groups.get("code", ""),
                    file_path=groups.get("file"),
                    line_number=int(groups["line"]) if groups.get("line") else None,
                    column=int(groups["col"]) if groups.get("col") else None,
                )

                # Extract context (surrounding lines)
                start = max(0, match.start() - 200)
                end = min(len(logs), match.end() + 200)
                error.context = logs[start:end]

                errors.append(error)
                detected_type = error_type

    # If no structured errors found, try to extract error summary
    if not errors:
        errors = _extract_generic_errors(logs)

    result = ParsedErrors(
        errors=errors,
        raw_logs=logs,
        error_type=detected_type if errors else "unknown",
    )

    logger.info(
        f"Parsed {len(errors)} errors of type '{result.error_type}' "
        f"from {len(result.affected_files)} files"
    )

    return result


def _extract_generic_errors(logs: str) -> list[ParsedError]:
    """Extract generic error patterns when specific parsers don't match."""
    errors: list[ParsedError] = []

    # Look for common error indicators
    error_indicators = [
        re.compile(r"^error\[.*?\]:\s*(.+)$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^Error:\s*(.+)$", re.MULTILINE),
        re.compile(r"^fatal:\s*(.+)$", re.MULTILINE | re.IGNORECASE),
        re.compile(r"^(?:npm |yarn )?ERR!\s*(.+)$", re.MULTILINE),
    ]

    for pattern in error_indicators:
        matches = pattern.finditer(logs)
        for match in matches:
            errors.append(
                ParsedError(
                    error_type="generic",
                    message=match.group(1).strip(),
                )
            )

    return errors[:10]  # Limit to first 10 generic errors
