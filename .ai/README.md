# Multi-IA Orchestrator

Shared contract for OpenAI/ChatGPT, Claude/Anthropic and Grok/xAI.

Principles:
- No model is trusted as the sole source of truth.
- The repository is the shared workspace.
- Every run records provider status and outputs.
- Code changes require git apply --check before application.
- Tests are run only when a supported command is detected.
- Secrets never enter the repository.

Required GitHub Actions secrets:
- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- XAI_API_KEY

Optional repository variables:
- OPENAI_MODEL (default: gpt-5)
- CLAUDE_MODEL (must be set)
- GROK_MODEL (default: grok-4.7)
