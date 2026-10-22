# Agent-assisted setup

For Claude Code, Codex and other agents with local filesystem and terminal access.
Read AGENTS.md / AGENT.md first. Use [SETUP.md](SETUP.md) for the full human guide;
keep the conversation short and explain only the next relevant action.

## 1. Inspect before changing anything

- Confirm native 64-bit Windows and an NVIDIA CUDA GPU. The workflow targets a
  16 GB VRAM budget; CPU-only generation and other platforms are not verified.
- Run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -CheckOnly`.
  This checks Git, uv, Blender and the NVIDIA driver without downloading models,
  creating an environment, starting a server or generating an asset.
- Check free space (roughly 40 GB for a fresh setup, more for saved jobs).
  Initial setup needs internet access, around 12.3 GB of shape weights plus
  foreground models and dependencies. Read upstream license notices.
- Reuse a compatible existing installation. Inspect `.venv`, `models/`, and
  `work/vendor/`; preserve jobs, caches and local configuration. Do not upgrade
  drivers, global Python or Strata as a side effect of project setup.

## 2. Resolve only missing prerequisites

Git for Windows, uv and Blender must be installed first. Link the relevant
installer in SETUP.md and help the user complete missing steps. Installation
outside the project follows the user's permissions and the agent host's policy.
Reopen the shell or refresh PATH after installing a tool. Use LOCAL3D_BLENDER
for a nonstandard Blender path. Blender 5.2 is the verified version.

Do not introduce Node.js, Docker, WSL, a separate Python installation or Strata
for the default labelled-photo workflow. The project installs its own Python.
If the hardware cannot support the workflow, explain that before large downloads.

## 3. Install through one entry point

From the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1
```

The equivalent human entry point is **Setup Local 3D.cmd**. Use `-NoStart` when
the user wants installation without opening the app. The script delegates to
the existing pinned setup, checks CUDA/imports and starts the app on success.
It does not run inference. It can be rerun after a failed download; inspect the
failure first and preserve caches. Do not delete the environment or redownload
everything by default. Never retry crashed/OOM generation as installation repair.

## 4. Verify and hand off

- Require a successful installer exit, not just a running process. The
  environment check must report CUDA available. Run it separately if needed:
  `.\.venv\Scripts\python.exe -B scripts/check_shape_environment.py`.
- If started, request `http://127.0.0.1:8765/api/health`; require `ready`,
  `single_view_ready` and `multiview_ready`. HTTP readiness does not establish
  enough free GPU memory, visual quality or a successful generated asset.
- Tell the user to open http://127.0.0.1:8765, choose **Try an example**, and
  click **Generate asset** when they want a first generation. Generation needs
  at least 8 GiB available RAM and 10,000 MiB free GPU memory at the start.
- Explain that the browser can close while jobs continue. Later launches use
  **Start Local 3D.cmd**. Link the Unity instructions in SETUP.md.
- Summarize what passed, what remains, and any user action. Keep machine paths,
  usernames and hardware evidence in ignored `work/`, never in tracked docs.

Optional extra-photo recognition requires a compatible existing Strata setup;
follow MORE_ANGLES.md separately. Do not promise the installer provisions it.

## If setup fails

Stop at the failed stage and explain the specific error. Follow SETUP.md's
troubleshooting table. Check `work/web-app-errors.log` for startup failures.
Preserve runtime files. Recheck PATH, driver/CUDA availability and Blender
discovery before rerunning setup. A healthy HTTP response is not proof of a
completed generation or Unity import.
