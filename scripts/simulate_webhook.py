#!/usr/bin/env python3
"""
Simulate a GitHub webhook for local testing.

Usage:
    python scripts/simulate_webhook.py --run-id 12345 --repo owner/repo
"""

import argparse
import hashlib
import hmac
import json
import os

import httpx


def main():
    parser = argparse.ArgumentParser(description="Simulate GitHub webhook")
    parser.add_argument("--url", default="http://localhost:8000/webhook/github")
    parser.add_argument("--run-id", type=int, required=True, help="Workflow run ID")
    parser.add_argument("--repo", required=True, help="Repository (owner/repo)")
    parser.add_argument("--branch", default="main", help="Branch name")
    parser.add_argument("--sha", default="abc123def456", help="Commit SHA")
    parser.add_argument(
        "--secret", default=None, help="Webhook secret (or use GITHUB_WEBHOOK_SECRET env)"
    )

    args = parser.parse_args()

    secret = args.secret or os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        print("Error: Webhook secret required (--secret or GITHUB_WEBHOOK_SECRET)")
        return 1

    payload = {
        "action": "completed",
        "workflow_run": {
            "id": args.run_id,
            "conclusion": "failure",
            "head_branch": args.branch,
            "head_sha": args.sha,
            "html_url": f"https://github.com/{args.repo}/actions/runs/{args.run_id}",
        },
        "repository": {
            "full_name": args.repo,
        },
    }

    payload_bytes = json.dumps(payload).encode()
    signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
    )

    print(f"Sending webhook to {args.url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    response = httpx.post(
        args.url,
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature,
            "X-GitHub-Event": "workflow_run",
        },
    )

    print(f"\nResponse status: {response.status_code}")
    print(f"Response body: {response.json()}")

    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    exit(main())
