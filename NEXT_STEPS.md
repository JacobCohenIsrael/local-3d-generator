# Current checkpoint: local MCP bridge

- MCP.md documents local stdio connection for Claude/Codex and consuming-project
  instructions. scripts/mcp_config.py prints configuration without changing it.
- scripts/mcp_server.py uses the official SDK in an isolated uv environment.
  It exposes availability, list/get job, submission, cancellation and downloads.
- Health distinguishes MCP liveness from app/model readiness; no GPU worker is
  created by MCP. Generation uses the existing bounded HTTP queue.
- HTTP health now identifies the service, and GET /api/jobs/ID reads older jobs
  independently of the latest-100 history window. Restart an older running app.
- Tests use a temporary queue without its worker; no inference or Unity import.
- Documentation/setup simplification is isolated on codex/welcoming-setup.
- Preserve runtime data, model caches, static/unrigged limitations and private
  host evidence. Public configurations should contain no personal paths.

Verification: all 45 existing checks passed; all 7 MCP checks passed, including
SDK stdio, app restart recovery and partial-download cleanup. The standard
suite skips its SDK-only check without MCP installed; the isolated SDK run
passed it. No model generation or fresh model installation was run.
