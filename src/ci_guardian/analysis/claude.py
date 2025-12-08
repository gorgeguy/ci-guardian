"""Claude API integration for error analysis and fix generation."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from ci_guardian.analysis.parser import ParsedErrors
from ci_guardian.config import get_settings
from ci_guardian.github.repo import get_relevant_files

logger = logging.getLogger(__name__)


@dataclass
class FileChange:
    """A single file change to apply."""

    file_path: str
    original_content: str
    new_content: str


@dataclass
class FixResult:
    """Result of Claude's analysis and fix generation."""

    can_fix: bool
    description: str
    changes: list[FileChange] = field(default_factory=list)
    confidence: float = 0.0
    analysis: str = ""


ANALYSIS_PROMPT = """You are CI Guardian, an automated CI failure analysis and repair system.

Analyze the following CI failure and generate a fix if possible.

## Error Information

Error Type: {error_type}
Affected Files: {affected_files}

## CI Logs (relevant sections)

```
{logs}
```

## Source Files

{source_files}

## Task

1. Analyze the error to understand the root cause
2. Determine if this is a fixable issue (type errors, lint issues, simple test fixes)
3. If fixable, generate the corrected code

## Response Format

Respond with a JSON object in this exact format:

```json
{{
    "can_fix": true/false,
    "confidence": 0.0-1.0,
    "analysis": "Brief explanation of the error and root cause",
    "description": "What was fixed (for PR description)",
    "changes": [
        {{
            "file_path": "path/to/file.py",
            "new_content": "entire corrected file content"
        }}
    ]
}}
```

Guidelines:
- Only set can_fix=true if you're confident the fix is correct
- For type errors: add proper type annotations or fix type mismatches
- For lint errors: apply the required formatting/style fixes
- For test failures: only fix if the issue is clear and deterministic
- Do NOT fix: logic bugs, security issues, or complex refactors
- Keep changes minimal - only fix what's needed
- Preserve the original code style and formatting
"""


async def analyze_failure(errors: ParsedErrors, repo_path: Path) -> FixResult:
    """
    Analyze CI failure using Claude and generate a fix.

    Args:
        errors: Parsed error information
        repo_path: Path to the cloned repository

    Returns:
        FixResult with analysis and potential fix
    """
    settings = get_settings()

    # Get relevant source files
    source_files = await get_relevant_files(repo_path, errors.affected_files)

    # Format source files for prompt
    formatted_sources = ""
    for file_path, content in source_files.items():
        formatted_sources += f"\n### {file_path}\n```\n{content}\n```\n"

    if not formatted_sources:
        formatted_sources = "(No relevant source files found)"

    # Format logs (truncate if needed)
    logs = errors.raw_logs
    if len(logs) > 15000:
        logs = logs[:15000] + "\n... [truncated]"

    prompt = ANALYSIS_PROMPT.format(
        error_type=errors.error_type,
        affected_files=", ".join(errors.affected_files) or "Unknown",
        logs=logs,
        source_files=formatted_sources,
    )

    logger.info(f"Sending analysis request to Claude ({settings.claude_model})")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=8192,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        # Extract the response text
        content_block = response.content[0]
        if not hasattr(content_block, "text"):
            raise ValueError("Unexpected response format from Claude API")
        response_text: str = content_block.text  # type: ignore[union-attr]

        # Parse the JSON from the response
        result = _parse_claude_response(response_text, source_files)

        logger.info(
            f"Claude analysis complete: can_fix={result.can_fix}, "
            f"confidence={result.confidence}, changes={len(result.changes)}"
        )

        return result

    except anthropic.APIError as e:
        logger.error(f"Claude API error: {e}")
        return FixResult(
            can_fix=False,
            description="",
            analysis=f"API error: {e}",
        )


def _parse_claude_response(response_text: str, source_files: dict[str, str]) -> FixResult:
    """Parse Claude's JSON response into a FixResult."""
    # Try to extract JSON from the response
    json_match = None

    # Look for JSON block
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        if end > start:
            json_match = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        if end > start:
            json_match = response_text[start:end].strip()
    else:
        # Try to find raw JSON
        try:
            start = response_text.index("{")
            end = response_text.rindex("}") + 1
            json_match = response_text[start:end]
        except ValueError:
            pass

    if not json_match:
        logger.warning("Could not extract JSON from Claude response")
        return FixResult(
            can_fix=False,
            description="",
            analysis="Failed to parse Claude response",
        )

    try:
        data = json.loads(json_match)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse Claude JSON: {e}")
        return FixResult(
            can_fix=False,
            description="",
            analysis=f"JSON parse error: {e}",
        )

    # Build FileChange objects
    changes = []
    for change_data in data.get("changes", []):
        file_path = change_data.get("file_path", "")
        new_content = change_data.get("new_content", "")

        if file_path and new_content:
            original = source_files.get(file_path, "")
            changes.append(
                FileChange(
                    file_path=file_path,
                    original_content=original,
                    new_content=new_content,
                )
            )

    return FixResult(
        can_fix=data.get("can_fix", False),
        description=data.get("description", ""),
        changes=changes,
        confidence=data.get("confidence", 0.0),
        analysis=data.get("analysis", ""),
    )
