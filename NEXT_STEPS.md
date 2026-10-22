# Current checkpoint: welcoming setup

- README is a short welcome with agent-assisted and human setup routes.
- SETUP.md preserves the detailed installation, usage, troubleshooting and
  verification material formerly in README.
- SETUP_AGENT.md guides Claude/Codex and other agents through prerequisite
  discovery, pinned installation, verification and handoff without inference.
- Setup Local 3D.cmd / scripts/install.ps1 provide one project setup entry point
  with prerequisite checks; -CheckOnly performs checks without installation.
- Git, uv, NVIDIA drivers and Blender remain external prerequisites. Large
  model downloads and the supported Windows/CUDA hardware still apply.
- Existing static mesh, photo-color and Unity-import limitations remain in
  SETUP.md and the previous feature guides. Preserve jobs and private runtime data.
- MCP work is isolated on the separate codex/local3d-mcp branch/worktree.

Verification: prerequisite-only installer check and PowerShell syntax passed;
local documentation links resolve. A full model installation was not rerun.
