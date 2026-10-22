# Current checkpoint: welcoming setup and local MCP

## Completed

- Both setup and MCP branches are integrated into main. README stays short and
  links the human walkthrough, agent setup guide and MCP connection guide.
- SETUP.md preserves the detailed installation, usage, troubleshooting and
  verification material. SETUP_AGENT.md guides Claude/Codex through discovery,
  pinned installation, verification and handoff without starting inference.
- Setup Local 3D.cmd / scripts/install.ps1 provide one project setup entry point.
  -CheckOnly checks prerequisites without downloads or starting the app.
- MCP.md documents local stdio connection and instructions for consuming projects.
  scripts/mcp_config.py prints configuration without modifying agent settings.
- The MCP bridge uses an isolated SDK environment and the existing HTTP queue
  for availability, job listing/status, generation, cancellation and downloads.
- Health distinguishes MCP liveness from app/model readiness. The HTTP service
  identifier and individual-job endpoint support reliable checks and old jobs.
- Existing history reuse, fresh drafts, setting help, low-poly export and photo
  color features remain in place. Preserve jobs, model caches and local config.

## Verification and next action

- The merged Python suite ran 52 checks: 51 passed and its SDK-only check was
  skipped in the generation environment. All seven MCP checks passed with the
  SDK, including stdio, app restart recovery and partial-download cleanup.
- The browser interaction test, installer prerequisite check and merged
  documentation links passed. Installer syntax was verified on the setup branch.
  A full model installation and GPU generation were not repeated.
- To use MCP with an older running app, restart it when no job is active,
  follow MCP.md and call local3d_status.
- Git, uv, NVIDIA drivers and Blender remain external prerequisites. Windows/CUDA
  hardware and large model downloads are still required. Models are static and
  unrigged; photo colors can have seams and estimated regions. Actual Unity
  Editor import remains a manual acceptance step.
