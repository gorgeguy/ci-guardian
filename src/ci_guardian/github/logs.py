"""GitHub workflow log fetching."""

import asyncio
import logging

from ci_guardian.config import get_settings

logger = logging.getLogger(__name__)


async def fetch_workflow_logs(repo_full_name: str, run_id: int) -> str:
    """
    Fetch failed workflow logs using GitHub CLI.

    Args:
        repo_full_name: Repository in owner/repo format
        run_id: The workflow run ID

    Returns:
        The log output as a string, truncated if necessary
    """
    settings = get_settings()

    # Use gh CLI to fetch failed logs
    cmd = ["gh", "run", "view", str(run_id), "--log-failed", "--repo", repo_full_name]

    logger.info(f"Fetching logs for {repo_full_name} run {run_id}")

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={"GH_TOKEN": settings.github_token, "PATH": "/usr/bin:/usr/local/bin"},
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        error_msg = stderr.decode("utf-8", errors="replace")
        logger.error(f"Failed to fetch logs: {error_msg}")
        raise RuntimeError(f"Failed to fetch workflow logs: {error_msg}")

    logs = stdout.decode("utf-8", errors="replace")

    # Truncate if too large
    if len(logs) > settings.max_log_size:
        logger.warning(f"Truncating logs from {len(logs)} to {settings.max_log_size} chars")
        # Keep the end of the logs (usually where errors are)
        logs = (
            f"[... truncated {len(logs) - settings.max_log_size} characters ...]\n"
            + logs[-settings.max_log_size :]
        )

    return logs


async def fetch_workflow_logs_via_api(repo_full_name: str, run_id: int) -> str:
    """
    Alternative: Fetch logs via GitHub API.

    This is a fallback if gh CLI is not available.
    """
    import httpx

    settings = get_settings()
    owner, repo = repo_full_name.split("/")

    async with httpx.AsyncClient() as client:
        # First, get the jobs for this run
        jobs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        headers = {
            "Authorization": f"Bearer {settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        response = await client.get(jobs_url, headers=headers)
        response.raise_for_status()
        jobs_data = response.json()

        all_logs = []

        # Fetch logs for failed jobs
        for job in jobs_data.get("jobs", []):
            if job.get("conclusion") == "failure":
                job_id = job["id"]
                logs_url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"

                log_response = await client.get(logs_url, headers=headers, follow_redirects=True)

                if log_response.status_code == 200:
                    all_logs.append(f"=== Job: {job['name']} ===\n{log_response.text}")

        return "\n\n".join(all_logs) if all_logs else "No failed job logs found"
