"""Slack notification integration."""

import logging

import httpx

from ci_guardian.config import get_settings

logger = logging.getLogger(__name__)


async def send_failure_notification(
    repo: str,
    branch: str,
    run_id: int,
    run_url: str,
) -> None:
    """
    Send a Slack notification about a CI failure.

    Args:
        repo: Repository name (owner/repo format)
        branch: Branch name
        run_id: Workflow run ID
        run_url: URL to the failed run
    """
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔴 CI Failure Detected",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Repository:*\n{repo}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Branch:*\n`{branch}`",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "CI Guardian is analyzing the failure and will attempt to create a fix.",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Run",
                            "emoji": True,
                        },
                        "url": run_url,
                        "style": "danger",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Run ID: {run_id}",
                    },
                ],
            },
        ],
    }

    await _send_slack_message(message)


async def send_pr_notification(
    repo: str,
    branch: str,
    pr_url: str,
    fix_description: str,
) -> None:
    """
    Send a Slack notification about a fix PR being created.

    Args:
        repo: Repository name (owner/repo format)
        branch: Original branch name
        pr_url: URL to the created PR
        fix_description: Description of what was fixed
    """
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🟢 Fix PR Created",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Repository:*\n{repo}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Branch:*\n`{branch}`",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*What was fixed:*\n{fix_description}",
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Review PR",
                            "emoji": True,
                        },
                        "url": pr_url,
                        "style": "primary",
                    },
                ],
            },
        ],
    }

    await _send_slack_message(message)


async def send_error_notification(
    repo: str,
    branch: str,
    run_id: int,
    error_message: str,
) -> None:
    """
    Send a Slack notification when CI Guardian fails to create a fix.

    Args:
        repo: Repository name
        branch: Branch name
        run_id: Workflow run ID
        error_message: Description of why the fix failed
    """
    message = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "⚠️ CI Guardian Could Not Fix",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Repository:*\n{repo}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Branch:*\n`{branch}`",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Reason:*\n{error_message}",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Run ID: {run_id} • Manual intervention required",
                    },
                ],
            },
        ],
    }

    await _send_slack_message(message)


async def _send_slack_message(message: dict) -> None:
    """Send a message to Slack via webhook."""
    settings = get_settings()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                settings.slack_webhook_url,
                json=message,
                timeout=10.0,
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
        except httpx.HTTPError as e:
            logger.error(f"Failed to send Slack notification: {e}")
            # Don't raise - notifications are best-effort
