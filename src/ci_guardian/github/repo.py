"""Repository cloning operations."""

import asyncio
import logging
import tempfile
from pathlib import Path

from ci_guardian.config import get_settings

logger = logging.getLogger(__name__)


async def clone_repository(repo_full_name: str, branch: str, commit_sha: str) -> Path:
    """
    Clone a repository to a temporary directory.

    Args:
        repo_full_name: Repository in owner/repo format
        branch: The branch to checkout
        commit_sha: The specific commit to checkout

    Returns:
        Path to the cloned repository
    """
    settings = get_settings()

    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="ci-guardian-"))
    repo_path = temp_dir / repo_full_name.replace("/", "-")

    # Clone with gh CLI
    clone_url = f"https://github.com/{repo_full_name}.git"

    logger.info(f"Cloning {repo_full_name} to {repo_path}")

    # Clone the repository
    clone_cmd = [
        "git",
        "clone",
        "--depth=50",
        "--branch",
        branch,
        clone_url,
        str(repo_path),
    ]

    env = {
        "GIT_ASKPASS": "echo",
        "GIT_TERMINAL_PROMPT": "0",
        "GH_TOKEN": settings.github_token,
        "PATH": "/usr/bin:/usr/local/bin",
    }

    # For authenticated clone, we need to use the token
    auth_clone_url = (
        f"https://x-access-token:{settings.github_token}@github.com/{repo_full_name}.git"
    )
    clone_cmd[5] = auth_clone_url

    process = await asyncio.create_subprocess_exec(
        *clone_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace")
        logger.error(f"Failed to clone repository: {error_msg}")
        raise RuntimeError(f"Failed to clone repository: {error_msg}")

    # Checkout the specific commit
    checkout_cmd = ["git", "checkout", commit_sha]

    process = await asyncio.create_subprocess_exec(
        *checkout_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=repo_path,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace")
        logger.warning(f"Failed to checkout commit {commit_sha}: {error_msg}")
        # Continue anyway - we'll work with HEAD of the branch

    logger.info(f"Successfully cloned {repo_full_name}")
    return repo_path


async def get_relevant_files(repo_path: Path, error_files: list[str]) -> dict[str, str]:
    """
    Read the content of files relevant to the error.

    Args:
        repo_path: Path to the cloned repository
        error_files: List of file paths mentioned in errors

    Returns:
        Dict mapping file paths to their contents
    """
    settings = get_settings()
    files_content: dict[str, str] = {}

    for file_path in error_files[: settings.max_context_files]:
        full_path = repo_path / file_path
        if full_path.exists() and full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                # Truncate very large files
                if len(content) > 10000:
                    content = content[:10000] + "\n... [truncated]"
                files_content[file_path] = content
            except Exception as e:
                logger.warning(f"Failed to read {file_path}: {e}")

    return files_content
