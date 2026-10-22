# Local 3D Generator

**Your photos, turned into a 3D asset on your own PC.**

Drop in reference images, generate a mesh, then download an FBX with photo
colors for Unity. A local browser app handles the queue, preview and exports.
Your images and results stay on your machine.

- Start with one photo, or use front / left / back / right views.
- Preview, adjust and reuse previous creations.
- Export an FBX + colors ZIP or a Blender project.

Models are static and unrigged. Results need visual review; this is generative
reconstruction, not a measured scan.

## Get started

You need **64-bit Windows, an NVIDIA CUDA GPU, Git, uv and Blender**.
The supported workflow targets **16 GB VRAM**; allow roughly **40 GB free disk**
for setup. Initial installation downloads large models (about 12.3 GB of shape
weights, plus dependencies). See the [requirements and installation guide](SETUP.md#requirements).

Already have the prerequisites? Get the project:

```powershell
git clone https://github.com/JacobCohenIsrael/local-3d-generator.git
cd local-3d-generator
& ".\Setup Local 3D.cmd"
```

Or, after cloning, double-click
**[Setup Local 3D.cmd](Setup%20Local%203D.cmd)**. It checks your setup, installs
the project environment and opens the app. Later, use
**[Start Local 3D.cmd](Start%20Local%203D.cmd)**.

Prefer a walkthrough? Follow the **[step-by-step setup and user guide](SETUP.md)**.
No agent, Node.js, Docker or Strata is needed for labelled reference photos.

## Let my agent set me up

Open this repository in Claude Code, Codex or another coding agent and paste:

```text
Help me set up Local 3D Generator. Read AGENTS.md, AGENT.md and SETUP_AGENT.md,
then inspect my prerequisites and follow the setup guide. Reuse compatible
existing tools and models, explain anything I need to install, and verify
the local app is ready. Do not start a generation until I ask.
```

The **[agent setup guide](SETUP_AGENT.md)** includes checks, recovery steps and
a clear handoff. The installer handles the project environment; prerequisites
and large model downloads still make this more than a tiny package install.

## Explore

- [Use the app and import into Unity](SETUP.md#generate-an-asset)
- [Troubleshooting](SETUP.md#troubleshooting)
- [Extra photos and optional Strata vision](MORE_ANGLES.md)
- [Photo color baking and its limits](docs/PHOTO_BAKING.md)
- [Architecture and verification](WEB_APP.md) · [Current checkpoint](NEXT_STEPS.md)

## License

Project code and documentation use the [MIT License](LICENSE).
[Tencent models](https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1), Blender
and other dependencies retain their own licenses. Model weights are downloaded
separately and are not included in this repository.
