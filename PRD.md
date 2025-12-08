# PRD: CI Guardian - Automated CI Failure Detection & Remediation

## Executive Summary

**CI Guardian** is a webhook-based service that monitors GitHub Actions CI pipelines, automatically analyzes failures using Claude, generates fixes, creates pull requests, and notifies developers via Slack. It transforms CI failures from blocking events into self-healing opportunities.

## Problem Statement

When CI pipelines fail, developers must:
1. Notice the failure (often delayed)
2. Navigate to GitHub Actions to view logs
3. Parse through verbose logs to identify the issue
4. Manually create a fix branch
5. Push changes and create a PR

This manual process wastes developer time and delays delivery. Many failures (type errors, lint issues, formatting) are deterministic and could be fixed automatically.

## Solution Overview

CI Guardian receives GitHub webhooks when workflows complete, and for failures:
1. **Detects** the failure in real-time via webhook
2. **Fetches** the failure logs using GitHub CLI
3. **Analyzes** the error using Claude to understand the root cause
4. **Generates** a fix by examining the codebase and producing a patch
5. **Creates** a PR automatically with the fix
6. **Notifies** the team via Slack with failure details and PR link

## Architecture

```
┌─────────────────┐                     ┌──────────────────────┐
│  GitHub Actions │──webhook (HTTPS)───▶│    CI Guardian       │
│  workflow_run   │                     │    (FastAPI)         │
└─────────────────┘                     └──────────┬───────────┘
                                                   │
         ┌──────────────────┬──────────────────────┼──────────────────┬──────────────────┐
         │                  │                      │                  │                  │
         ▼                  ▼                      ▼                  ▼                  ▼
┌─────────────┐    ┌──────────────┐      ┌──────────────┐    ┌──────────────┐   ┌──────────────┐
│ GitHub API  │    │  Clone Repo  │      │ Claude API   │    │ Create PR    │   │ Slack API    │
│ (get logs)  │    │  (temp dir)  │      │ (analyze)    │    │ (gh CLI)     │   │ (notify)     │
└─────────────┘    └──────────────┘      └──────────────┘    └──────────────┘   └──────────────┘
```

## User Stories

### US-1: Automatic Type Error Fixes
**As a** developer with a failing CI due to type errors
**I want** CI Guardian to automatically create a fix PR
**So that** I can review and merge the fix without manual debugging

**Acceptance Criteria:**
- Pyright/TypeScript errors are parsed from logs
- Claude generates correct type annotations/fixes
- PR is created with clear description of what was fixed

### US-2: Lint/Format Auto-Fix
**As a** developer who forgot to run formatters
**I want** formatting issues to be auto-fixed
**So that** CI doesn't block on trivial issues

**Acceptance Criteria:**
- Detects ruff/eslint/prettier failures
- Runs formatters and creates fix PR
- Works for both Python and TypeScript

### US-3: Slack Notifications
**As a** team lead
**I want** to be notified in Slack when CI fails and when fixes are created
**So that** I have visibility into pipeline health

**Acceptance Criteria:**
- Slack message on CI failure with error summary
- Follow-up message with PR link when fix is ready
- Messages include repo name, branch, error type

### US-4: Test Failure Analysis
**As a** developer with failing tests
**I want** Claude to analyze the failure and suggest fixes
**So that** I understand what broke and how to fix it

**Acceptance Criteria:**
- Test output is parsed and summarized
- Claude identifies likely cause
- Fix PR is created if the fix is straightforward

## Functional Requirements

### FR-1: Webhook Handler
- Accept GitHub `workflow_run` webhooks
- Validate webhook signature using secret
- Filter for `conclusion: failure` events
- Queue processing for async handling

### FR-2: Log Fetching
- Use `gh run view --log-failed` or GitHub API
- Parse and extract relevant error messages
- Handle large log files (truncation/summarization)
- Cache logs to avoid redundant fetches

### FR-3: Claude Integration
- Send error context to Claude API
- Include relevant source files in context
- Request structured output (diagnosis + fix)
- Handle rate limits and retries

### FR-4: Code Modification
- Clone repository to temporary directory
- Checkout the failing branch
- Apply Claude-suggested fixes
- Run local validation (lint, type check) before PR

### FR-5: PR Creation
- Create fix branch: `ci-guardian/fix-{run_id}`
- Commit with descriptive message
- Create PR using `gh pr create`
- Link PR to original failure

### FR-6: Slack Notifications
- Send webhook on failure detection
- Send follow-up on PR creation
- Include actionable links (PR, logs, run)
- Support channel configuration per repo

## Non-Functional Requirements

### NFR-1: Performance
- Webhook response < 2 seconds (async processing)
- Total fix turnaround < 5 minutes
- Support concurrent processing of multiple failures

### NFR-2: Security
- Validate GitHub webhook signatures (HMAC SHA-256)
- Store secrets securely (environment variables)
- Minimal GitHub token permissions (repo, workflow)
- No persistent storage of source code

### NFR-3: Reliability
- Idempotent webhook handling (dedupe by run ID)
- Retry failed API calls with exponential backoff
- Graceful degradation (notify even if fix fails)

### NFR-4: Observability
- Structured logging (JSON format)
- Metrics: failures received, fixes attempted, PRs created
- Health check endpoint

## Technical Specifications

### Tech Stack
- **Runtime**: Python 3.12+
- **Framework**: FastAPI
- **Package Manager**: uv
- **AI**: Claude API (Anthropic)
- **GitHub**: gh CLI + PyGithub
- **Notifications**: Slack Incoming Webhooks

### Project Structure
```
ci-guardian/
├── src/
│   └── ci_guardian/
│       ├── __init__.py
│       ├── main.py           # FastAPI app entry
│       ├── config.py         # Settings (Pydantic)
│       ├── webhook/
│       │   ├── handler.py    # Webhook endpoint
│       │   └── validator.py  # Signature validation
│       ├── github/
│       │   ├── logs.py       # Log fetching
│       │   ├── repo.py       # Repo cloning
│       │   └── pr.py         # PR creation
│       ├── analysis/
│       │   ├── claude.py     # Claude API client
│       │   ├── parser.py     # Log parsing
│       │   └── fixer.py      # Code modification
│       └── notifications/
│           └── slack.py      # Slack integration
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── Dockerfile
├── fly.toml               # Fly.io deployment
└── CLAUDE.md              # Development guide
```

### Configuration (Environment Variables)
```bash
# Required
GITHUB_WEBHOOK_SECRET=xxx          # Webhook signature validation
GITHUB_TOKEN=xxx                   # GitHub API access (repo, workflow)
ANTHROPIC_API_KEY=xxx              # Claude API
SLACK_WEBHOOK_URL=xxx              # Slack notifications

# Optional
ALLOWED_REPOS=owner/repo1,owner/repo2  # Whitelist (default: all)
MAX_CONTEXT_FILES=20               # Limit files sent to Claude
LOG_LEVEL=INFO                     # Logging verbosity
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /webhook/github` | POST | GitHub webhook receiver |
| `GET /health` | GET | Health check |
| `GET /metrics` | GET | Prometheus metrics |

### Database
No persistent database required. All state is ephemeral:
- Webhook events processed immediately
- Temporary directories cleaned after PR creation
- Deduplication via in-memory cache (TTL: 1 hour)

## Deployment Options

### Option A: Fly.io (Recommended)
- Always-on server for webhook reliability
- ~$5/month for shared-cpu-1x
- Easy secrets management
- Public HTTPS endpoint for webhooks

### Option B: Cloud Run
- Serverless, scale-to-zero
- Pay per request
- Cold start latency (~2-5s acceptable for webhooks)

### Option C: Self-hosted
- Run on any server with public IP
- Use ngrok/cloudflared for local development

## GitHub Webhook Setup

1. Go to: Repository → Settings → Webhooks → Add webhook
2. Payload URL: `https://ci-guardian.fly.dev/webhook/github`
3. Content type: `application/json`
4. Secret: (generate and store in `GITHUB_WEBHOOK_SECRET`)
5. Events: Select "Workflow runs"

## Success Metrics

| Metric | Target |
|--------|--------|
| Failure detection latency | < 30 seconds |
| Fix success rate (simple issues) | > 80% |
| PR creation time | < 5 minutes |
| False positive rate | < 5% |

## Phase 1 MVP Scope

For the initial release, focus on:

1. ✅ Webhook handling with signature validation
2. ✅ Log fetching via `gh run view`
3. ✅ Claude analysis for error diagnosis
4. ✅ PR creation for simple fixes (type errors, lint)
5. ✅ Slack notifications (failure + PR created)

### Out of Scope for MVP
- Web dashboard
- Multi-repo configuration UI
- Custom fix strategies per project
- Integration with other CI systems (Jenkins, CircleCI)

## Future Enhancements (v2+)

- **Learning**: Track which fixes were merged vs rejected
- **Custom Rules**: Allow per-repo configuration of fix strategies
- **Dashboard**: Web UI to view history and configure repos
- **Other CI**: Support CircleCI, Jenkins, GitLab CI
- **PR Approval**: Request reviews automatically
- **Rollback Detection**: Detect if a fix PR caused new failures

## CLAUDE.md Template for New Project

```markdown
# CLAUDE.md

CI Guardian - Automated CI failure detection and remediation.

## Project Overview

Webhook-based service that monitors GitHub Actions, analyzes failures with Claude,
and automatically creates fix PRs.

## Development Commands

\`\`\`bash
# Install dependencies
uv sync

# Run development server
uv run ci-guardian serve

# Run tests
uv run --frozen pytest

# Type check
uv run --frozen pyright

# Lint
uv run --frozen ruff check . && uv run --frozen ruff format .
\`\`\`

## Architecture

- `webhook/` - GitHub webhook handling
- `github/` - GitHub API interactions (logs, PRs)
- `analysis/` - Claude integration and code fixing
- `notifications/` - Slack notifications

## Key Flows

1. Webhook received → Validate signature → Queue for processing
2. Fetch logs → Parse errors → Build context
3. Send to Claude → Get fix → Apply changes
4. Create PR → Notify Slack

## Testing

- Unit tests: Mock external APIs
- Integration tests: Use GitHub API in dry-run mode
- Manual testing: Use `scripts/simulate_webhook.py`
```

## Implementation Checklist

- [ ] Initialize project with uv + pyproject.toml
- [ ] Set up FastAPI app with health endpoint
- [ ] Implement webhook handler with signature validation
- [ ] Add GitHub log fetching via gh CLI
- [ ] Integrate Claude API for error analysis
- [ ] Implement repo cloning and code modification
- [ ] Add PR creation via gh CLI
- [ ] Set up Slack notifications
- [ ] Write unit tests for core components
- [ ] Create Dockerfile and fly.toml
- [ ] Deploy to Fly.io
- [ ] Configure webhook on target repository
