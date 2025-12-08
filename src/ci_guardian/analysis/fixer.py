"""Code modification and fix application."""

import asyncio
import logging
from pathlib import Path

from ci_guardian.analysis.claude import FileChange

logger = logging.getLogger(__name__)


async def apply_fix(repo_path: Path, changes: list[FileChange]) -> None:
    """
    Apply file changes to the repository.

    Args:
        repo_path: Path to the cloned repository
        changes: List of file changes to apply
    """
    logger.info(f"Applying {len(changes)} file changes")

    for change in changes:
        file_path = repo_path / change.file_path

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the new content
        logger.debug(f"Writing changes to {change.file_path}")
        file_path.write_text(change.new_content, encoding="utf-8")

    # Run validation after applying changes
    await _validate_changes(repo_path)


async def _validate_changes(repo_path: Path) -> None:
    """
    Run basic validation after applying changes.

    This runs linters/formatters to ensure the fix doesn't introduce new issues.
    """
    # Check for pyproject.toml to determine project type
    pyproject = repo_path / "pyproject.toml"
    package_json = repo_path / "package.json"

    if pyproject.exists():
        await _validate_python_project(repo_path)
    elif package_json.exists():
        await _validate_node_project(repo_path)


async def _validate_python_project(repo_path: Path) -> None:
    """Run Python validation (ruff format)."""
    # Try to run ruff format
    try:
        process = await asyncio.create_subprocess_exec(
            "ruff",
            "format",
            ".",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        # Also try ruff check --fix
        process = await asyncio.create_subprocess_exec(
            "ruff",
            "check",
            ".",
            "--fix",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        logger.debug("Ran ruff format and check on Python project")
    except FileNotFoundError:
        logger.debug("ruff not available for validation")


async def _validate_node_project(repo_path: Path) -> None:
    """Run Node.js validation (prettier, eslint --fix)."""
    # Try prettier
    try:
        process = await asyncio.create_subprocess_exec(
            "npx",
            "prettier",
            "--write",
            ".",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        logger.debug("Ran prettier on Node project")
    except FileNotFoundError:
        pass

    # Try eslint --fix
    try:
        process = await asyncio.create_subprocess_exec(
            "npx",
            "eslint",
            "--fix",
            ".",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        logger.debug("Ran eslint --fix on Node project")
    except FileNotFoundError:
        pass
