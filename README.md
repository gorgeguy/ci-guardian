# CI Guardian

Automated CI failure detection and remediation for GitHub Actions.

CI Guardian monitors your GitHub Actions workflows and automatically analyzes failures, generates fixes, creates pull requests, and notifies your team via Slack.

## Features

- **Real-time failure detection** - Receives GitHub webhooks when workflows fail
- **Intelligent analysis** - Uses Claude to understand error root causes
- **Automatic fixes** - Generates and applies fixes for common issues:
  - Type errors (Pyright, TypeScript)
  - Lint issues (Ruff, ESLint)
  - Formatting problems
  - Simple test failures
- **Pull request creation** - Automatically creates PRs with descriptive commit messages
- **Slack notifications** - Keeps your team informed about failures and fixes

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- [GitHub CLI](https://cli.github.com/) (`gh`)
- GitHub token with `repo` and `workflow` permissions
- Anthropic API key
- Slack incoming webhook URL

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/ci-guardian.git
cd ci-guardian

# Install dependencies
uv sync
```

### Configuration

Create a `.env` file (or set environment variables):

```bash
# Required
GITHUB_WEBHOOK_SECRET=your-webhook-secret    # For validating GitHub webhooks
GITHUB_TOKEN=ghp_your-token                  # GitHub API access
ANTHROPIC_API_KEY=sk-ant-your-key            # Claude API key
SLACK_WEBHOOK_URL=https://hooks.slack.com/... # Slack notifications

# Optional
ALLOWED_REPOS=owner/repo1,owner/repo2        # Restrict to specific repos (default: all)
MAX_CONTEXT_FILES=20                         # Max files sent to Claude
LOG_LEVEL=INFO                               # Logging verbosity
CLAUDE_MODEL=claude-sonnet-4-20250514        # Claude model to use
```

### Running Locally

```bash
# Start the server
uv run ci-guardian serve --reload

# Or with custom host/port
uv run ci-guardian serve --host 0.0.0.0 --port 8080
```

For local development, expose your server using ngrok:

```bash
ngrok http 8000
# Use the ngrok URL for your GitHub webhook
```

## GitHub Webhook Setup

1. Go to your repository: **Settings** > **Webhooks** > **Add webhook**
2. Configure the webhook:
   - **Payload URL**: `https://your-domain.com/webhook/github`
   - **Content type**: `application/json`
   - **Secret**: Same value as `GITHUB_WEBHOOK_SECRET`
   - **Events**: Select "Workflow runs" only
3. Click **Add webhook**

## Deployment

### Fly.io (Recommended)

```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create app (first time)
fly apps create ci-guardian

# Set secrets
fly secrets set GITHUB_WEBHOOK_SECRET=xxx
fly secrets set GITHUB_TOKEN=xxx
fly secrets set ANTHROPIC_API_KEY=xxx
fly secrets set SLACK_WEBHOOK_URL=xxx

# Deploy
fly deploy
```

### Docker

```bash
# Build the image
docker build -t ci-guardian .

# Run with environment variables
docker run -p 8000:8000 \
  -e GITHUB_WEBHOOK_SECRET=xxx \
  -e GITHUB_TOKEN=xxx \
  -e ANTHROPIC_API_KEY=xxx \
  -e SLACK_WEBHOOK_URL=xxx \
  ci-guardian
```

## How It Works

```
GitHub Actions ----webhook----> CI Guardian (FastAPI)
(workflow fails)                      |
                                      v
                 +--------------------+--------------------+
                 |                    |                    |
                 v                    v                    v
           Fetch Logs         Analyze with Claude     Create PR
           (gh CLI)           (diagnose + fix)        (gh CLI)
                 |                    |                    |
                 +--------------------+--------------------+
                                      |
                                      v
                              Notify via Slack
```

1. **Webhook received** - GitHub sends a `workflow_run` event when a workflow completes
2. **Signature validation** - CI Guardian verifies the webhook signature (HMAC SHA-256)
3. **Filter failures** - Only failed workflows are processed
4. **Fetch logs** - Uses `gh run view --log-failed` to get failure logs
5. **Parse errors** - Extracts structured error information (file, line, message)
6. **Claude analysis** - Sends error context and source files to Claude for analysis
7. **Generate fix** - Claude produces corrected code if the fix is straightforward
8. **Create PR** - Commits changes and creates a pull request
9. **Slack notification** - Notifies the team about the failure and fix

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/webhook/github` | POST | GitHub webhook receiver |
| `/health` | GET | Health check endpoint |
| `/metrics` | GET | Prometheus-style metrics |

## Development

### Running Tests

```bash
# Run all tests
uv run --frozen pytest

# Run with coverage
uv run --frozen pytest --cov=ci_guardian

# Run specific test file
uv run --frozen pytest tests/unit/test_parser.py -v
```

### Code Quality

```bash
# Type checking
uv run --frozen pyright

# Linting
uv run --frozen ruff check .

# Formatting
uv run --frozen ruff format .

# Fix lint issues
uv run --frozen ruff check . --fix
```

### Simulating Webhooks

For testing without a real GitHub webhook:

```bash
python scripts/simulate_webhook.py
```

## Supported Error Types

CI Guardian can parse and fix:

| Error Type | Source | Auto-fix |
|------------|--------|----------|
| Type errors | Pyright, mypy, TypeScript | Yes |
| Lint errors | Ruff, ESLint | Yes |
| Format errors | Ruff, Prettier | Yes |
| Test failures | pytest, Jest | Limited |

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITHUB_WEBHOOK_SECRET` | Yes | - | Secret for webhook signature validation |
| `GITHUB_TOKEN` | Yes | - | GitHub token (needs `repo`, `workflow` scopes) |
| `ANTHROPIC_API_KEY` | Yes | - | Anthropic API key for Claude |
| `SLACK_WEBHOOK_URL` | Yes | - | Slack incoming webhook URL |
| `ALLOWED_REPOS` | No | `[]` (all) | Comma-separated list of allowed repos |
| `MAX_CONTEXT_FILES` | No | `20` | Maximum files to include in Claude context |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-20250514` | Claude model to use |
| `HOST` | No | `0.0.0.0` | Server host |
| `PORT` | No | `8000` | Server port |
| `MAX_LOG_SIZE` | No | `50000` | Max log size before truncation |

## Security

- Webhook signatures are validated using HMAC SHA-256
- Secrets are loaded from environment variables
- Source code is processed in temporary directories and cleaned up
- GitHub token requires minimal permissions (`repo`, `workflow`)

## Limitations

CI Guardian is designed for straightforward, deterministic fixes. It will **not** attempt to fix:

- Complex logic bugs
- Security vulnerabilities
- Large refactoring changes
- Issues requiring human judgment

When a fix cannot be generated, CI Guardian will still notify your team via Slack with the error analysis.

## License

Apache 2.0 - See [LICENSE](LICENSE) for details.
