"""GitHub webhook handler."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from ci_guardian.config import get_settings
from ci_guardian.webhook.validator import validate_github_signature

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory cache for deduplication (run_id -> timestamp)
_processed_runs: dict[int, float] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _cleanup_cache() -> None:
    """Remove expired entries from the deduplication cache."""
    import time

    current_time = time.time()
    expired = [
        run_id
        for run_id, timestamp in _processed_runs.items()
        if current_time - timestamp > _CACHE_TTL_SECONDS
    ]
    for run_id in expired:
        del _processed_runs[run_id]


async def process_workflow_failure(payload: dict[str, Any]) -> None:
    """
    Process a workflow failure in the background.

    This function:
    1. Fetches the failure logs
    2. Analyzes them with Claude
    3. Generates and applies a fix
    4. Creates a PR
    5. Notifies via Slack
    """
    from ci_guardian.analysis import analyze_failure, apply_fix, parse_error_logs
    from ci_guardian.github import clone_repository, create_fix_pr, fetch_workflow_logs
    from ci_guardian.notifications import send_failure_notification, send_pr_notification

    workflow_run = payload["workflow_run"]
    run_id = workflow_run["id"]
    repo_full_name = payload["repository"]["full_name"]
    branch = workflow_run["head_branch"]
    commit_sha = workflow_run["head_sha"]

    logger.info(f"Processing workflow failure: {repo_full_name} run {run_id}")

    try:
        # Notify about the failure
        await send_failure_notification(
            repo=repo_full_name,
            branch=branch,
            run_id=run_id,
            run_url=workflow_run["html_url"],
        )

        # Fetch and parse logs
        logs = await fetch_workflow_logs(repo_full_name, run_id)
        parsed_errors = parse_error_logs(logs)

        if not parsed_errors.errors:
            logger.info(f"No parseable errors found in run {run_id}")
            return

        # Clone the repository
        repo_path = await clone_repository(repo_full_name, branch, commit_sha)

        try:
            # Analyze with Claude
            fix_result = await analyze_failure(
                errors=parsed_errors,
                repo_path=repo_path,
            )

            if not fix_result.can_fix:
                logger.info(f"Claude determined fix is not feasible for run {run_id}")
                return

            # Apply the fix
            await apply_fix(repo_path, fix_result.changes)

            # Create PR
            pr_url = await create_fix_pr(
                repo_path=repo_path,
                repo_full_name=repo_full_name,
                run_id=run_id,
                fix_description=fix_result.description,
                original_branch=branch,
            )

            # Notify about the PR
            await send_pr_notification(
                repo=repo_full_name,
                branch=branch,
                pr_url=pr_url,
                fix_description=fix_result.description,
            )

            logger.info(f"Successfully created fix PR for run {run_id}: {pr_url}")

        finally:
            # Cleanup temporary directory
            import shutil

            shutil.rmtree(repo_path, ignore_errors=True)

    except Exception as e:
        logger.exception(f"Failed to process workflow failure {run_id}: {e}")


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
) -> dict[str, str]:
    """
    Handle incoming GitHub webhooks.

    Validates the signature, filters for workflow_run failure events,
    and queues processing in the background.
    """
    import time

    settings = get_settings()

    # Read raw body for signature validation
    body = await request.body()

    # Validate signature
    if not validate_github_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    payload = await request.json()

    # Only process workflow_run events
    if x_github_event != "workflow_run":
        logger.debug(f"Ignoring event type: {x_github_event}")
        return {"status": "ignored", "reason": "not a workflow_run event"}

    workflow_run = payload.get("workflow_run", {})
    action = payload.get("action")
    conclusion = workflow_run.get("conclusion")

    # Only process completed failures
    if action != "completed" or conclusion != "failure":
        logger.debug(f"Ignoring workflow_run: action={action}, conclusion={conclusion}")
        return {"status": "ignored", "reason": f"action={action}, conclusion={conclusion}"}

    # Check if repo is allowed
    repo_full_name = payload.get("repository", {}).get("full_name", "")
    if not settings.is_repo_allowed(repo_full_name):
        logger.warning(f"Repository not in allowed list: {repo_full_name}")
        return {"status": "ignored", "reason": "repository not allowed"}

    # Deduplicate
    run_id = workflow_run.get("id")
    _cleanup_cache()

    if run_id in _processed_runs:
        logger.info(f"Skipping duplicate run: {run_id}")
        return {"status": "ignored", "reason": "duplicate"}

    _processed_runs[run_id] = time.time()

    # Queue background processing
    logger.info(f"Queueing processing for run {run_id} in {repo_full_name}")
    background_tasks.add_task(process_workflow_failure, payload)

    return {"status": "accepted", "run_id": str(run_id)}
