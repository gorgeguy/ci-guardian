# CLAUDE.md

CI Guardian - Automated CI failure detection and remediation.

## Project Overview

Webhook-based service that monitors GitHub Actions, analyzes failures with Claude,
and automatically creates fix PRs.

## Development Commands

```bash
# Install dependencies
uv sync

# Run development server
uv run ci-guardian serve --reload

# Run tests
uv run --frozen pytest

# Run tests with coverage
uv run --frozen pytest --cov=ci_guardian

# Type check
uv run --frozen pyright

# Lint
uv run --frozen ruff check .

# Format
uv run --frozen ruff format .

# Fix lint issues
uv run --frozen ruff check . --fix
```

## Architecture

- `src/ci_guardian/` - Main package
  - `main.py` - FastAPI app entry point and CLI
  - `config.py` - Pydantic settings
  - `webhook/` - GitHub webhook handling
    - `handler.py` - Webhook endpoint and processing
    - `validator.py` - Signature validation (HMAC SHA-256)
  - `github/` - GitHub API interactions
    - `logs.py` - Log fetching via `gh` CLI
    - `repo.py` - Repository cloning
    - `pr.py` - Pull request creation
  - `analysis/` - Claude integration and code fixing
    - `claude.py` - Claude API client
    - `parser.py` - Log parsing and error extraction
    - `fixer.py` - Code modification
  - `notifications/` - Slack integration
    - `slack.py` - Slack webhook notifications

## Key Flows

1. **Webhook received** → Validate signature → Filter for failures → Queue for processing
2. **Fetch logs** → Parse errors → Extract affected files → Build context
3. **Send to Claude** → Get structured fix → Validate response
4. **Apply changes** → Run linters → Create branch → Commit → Push
5. **Create PR** → Notify Slack

## Environment Variables

Required:
- `GITHUB_WEBHOOK_SECRET` - Webhook signature validation
- `GITHUB_TOKEN` - GitHub API access (needs repo, workflow permissions)
- `ANTHROPIC_API_KEY` - Claude API key
- `SLACK_WEBHOOK_URL` - Slack incoming webhook URL

Optional:
- `ALLOWED_REPOS` - JSON array of allowed repos, e.g., `["owner/repo1"]`
- `MAX_CONTEXT_FILES` - Max files to send to Claude (default: 20)
- `LOG_LEVEL` - Logging level (default: INFO)
- `CLAUDE_MODEL` - Claude model to use (default: claude-sonnet-4-20250514)

## Testing

- Unit tests: `tests/unit/` - Mock external APIs
- Integration tests: `tests/integration/` - Use GitHub API in dry-run mode
- Manual testing: Use `scripts/simulate_webhook.py`

Run specific test:
```bash
uv run --frozen pytest tests/unit/test_parser.py -v
```

## Deployment

### Fly.io (recommended)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create app (first time only)
fly apps create ci-guardian

# Set secrets
fly secrets set GITHUB_WEBHOOK_SECRET=xxx
fly secrets set GITHUB_TOKEN=xxx
fly secrets set ANTHROPIC_API_KEY=xxx
fly secrets set SLACK_WEBHOOK_URL=xxx

# Deploy
fly deploy
```

### Local Development with ngrok

```bash
# Start the server
uv run ci-guardian serve --reload

# In another terminal, expose via ngrok
ngrok http 8000

# Use the ngrok URL for GitHub webhook configuration
```

## GitHub Webhook Setup

1. Go to Repository → Settings → Webhooks → Add webhook
2. Payload URL: `https://ci-guardian.fly.dev/webhook/github`
3. Content type: `application/json`
4. Secret: Same as `GITHUB_WEBHOOK_SECRET`
5. Events: Select "Workflow runs" only
