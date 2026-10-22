# Connect Local 3D to your agents

Use Local 3D Generator from another project in Claude Code, Codex or any MCP
client supporting local stdio servers. The bridge uses your existing app and
durable queue; it never starts another GPU worker or downloads shape weights.

## Connect once

1. Install the app using the README setup instructions. Start **Start Local 3D.cmd**.
   Restart an older running app after updating to this branch (the bridge uses
   the new service identifier and individual-job endpoint).
2. Generate a config block from the Local 3D repository in PowerShell:

   ```powershell
   uv run --no-project scripts/mcp_config.py --format claude
   # Or, for Codex:
   uv run --no-project scripts/mcp_config.py --format codex
   ```

   Copy the generated block into the client configuration of the project where
   you want to use the tool. It contains this checkout's absolute script path,
   so it works regardless of the consuming project's working directory. Regenerate
   it after moving the checkout. Keep machine-specific configuration untracked.
3. For Claude Code, merge the `local3d` entry under `mcpServers` in the consuming
   project's `.mcp.json`. For Codex, merge `[mcp_servers.local3d]` into its trusted
   project `.codex/config.toml`, or your user config. Preserve existing entries.
   Reload the client and approve its normal MCP workspace trust prompt if needed.
4. Ask the agent to call **local3d_status**. It should report `mcp_ready: true`,
   `app_reachable: true`, `app_ready: true`. Check `health.single_view_ready` and
   `health.multiview_ready` for installed model flags.

The client launches `uv run --script <repository>/scripts/mcp_server.py` over
stdio. Script metadata pins the MCP SDK in uv's isolated environment; it does
not install MCP packages into the GPU environment. The first launch needs internet
for these small dependencies. Ensure uv is on the agent client's PATH; use its
absolute executable path in the generated config if necessary.
For an app on another loopback port, generate config with `--port 8766`.

Example config shapes (replace `<repository>` with the real checkout path;
the generator does this for you):

```json
{
  "mcpServers": {
    "local3d": {
      "command": "uv",
      "args": ["run", "--script", "<repository>/scripts/mcp_server.py"]
    }
  }
}
```

```toml
[mcp_servers.local3d]
command = "uv"
args = ["run", "--script", "<repository>/scripts/mcp_server.py"]
```

## Let agents know it is available

Add this to the consuming project's AGENTS.md and/or CLAUDE.md:

```text
Local 3D Generator is available through the local3d MCP server when configured.
For reference-image to static-mesh tasks, call local3d_status first. If app_ready
is false, explain the reported setup/startup step; do not repeatedly reconnect.
Check the model flags too. Generate only when requested. Use generate_asset
with absolute local photo paths, then poll get_job by ID instead of resubmitting.
Do not automatically retry crashes or out-of-memory failures. Download the
package export to an agreed project location for Unity. Inspect quality;
models are static/unrigged and photo colors can have seams or unseen regions.
```

No automatic project discovery or config edits are performed. Local stdio requires
a client running on this computer with filesystem access; a cloud-only agent
cannot reach your machine's loopback address.

## Tools

| Tool | Purpose |
| --- | --- |
| `local3d_status` | Check bridge responsiveness, app reachability and model flags. |
| `list_jobs` | Read the latest 100 jobs, progress and available exports. |
| `get_job` | Read any job by ID, including older history and download URLs. |
| `generate_asset` | Submit image paths/settings; return a queued job ID immediately. |
| `cancel_job` | Cancel a queued/running job while retaining history and originals. |
| `download_asset` | Save an available export to an absolute destination without overwriting. |

Example `generate_asset` arguments (use real absolute image paths):

```json
{
  "name": "My prop",
  "views": {"front": "<photos>/front.png", "back": "<photos>/back.png"},
  "settings": {
    "quality": "balanced", "triangles": 5000, "height": 1.0,
    "texture": "photo_basecolor", "texture_size": 512, "max_attempts": 1
  }
}
```

Use `texture: photo_basecolor` explicitly for photo colors; the HTTP API default
is untextured. Optional `extra_photos` is a list of unlabelled absolute paths and
requires configured Strata vision. Paths refer to files on the MCP server's machine.
Image/settings validation, resource checks, queue limits, deadlines and cancellation
are the same as the browser. GPU work keeps running if the MCP client disconnects.
Submitting again creates a separate job; there is no automatic submission retry.
Poll every few seconds while working elsewhere; no long-running MCP call is required.

`download_asset` takes `job_id`, `kind` (usually `package` for the FBX + colors ZIP),
and `destination`. The parent directory must exist. It never extracts the ZIP,
overwrites files or imports directly into Unity. Download URLs are local to this
app session/port. A destination path is an explicit filesystem write, subject to
your agent client's permissions. Downloads have a 1 GiB cap and a 30-second socket timeout.

## Liveness and limits

This server pins the SDK v1 line and its handshake-based MCP lifecycle. Its
standard `ping` checks MCP connection liveness. It does **not** check the web app,
model availability or free VRAM. `local3d_status` adds that app-level health check
(model presence only, not VRAM). It remains callable while the app is offline,
and works again after the app starts without restarting the MCP bridge.
Newer MCP lifecycle revisions have changed ping handling; the SDK owns protocol
negotiation. Agents should use `local3d_status` for this app's availability.

The bridge only connects to `127.0.0.1`, disables proxies and redirects, and uses
the app's existing per-process token for mutations. Tokens stay inside the
bridge. This is a trusted local-user integration, not a remote authenticated
service. It cannot run shell commands, start the app or change global settings.

## Verify without generating

```powershell
uv run --no-project --with mcp==1.26.0 --with pillow==11.0.0 --with filelock==4.1.0 --with numpy==1.24.4 python -B -m unittest discover -s scripts -p test_mcp_server.py
```

These tests run a temporary HTTP queue without starting its worker. They cover
real SDK stdio initialization, ping, tool discovery, submission, status,
cancellation, offline handling, validation and export downloads. No neural
generation or Unity Editor import is claimed by these tests.

Sources: [MCP SDK v1](https://py.sdk.modelcontextprotocol.io/v1/),
[handshake-lifecycle ping](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/ping),
[Codex MCP configuration](https://developers.openai.com/codex/mcp/),
[Claude Code MCP configuration](https://code.claude.com/docs/en/mcp).
