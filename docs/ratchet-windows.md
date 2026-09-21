# Windows setup and observed limits

Ratchet's installed CLI, saved-root MCP startup, original retrieval, offline
replay, and fresh pytest reporter installation pass on Windows. These checks use
an isolated wheel environment outside the source checkout. They are separate
from a real Codex worker making a repair.

The real repair preflight eventually passed with Codex CLI
`0.155.0-alpha.2.6`, bundled with the tested desktop app, and Python `3.12.11`
installed under the workspace. Codex changed only the authored implementation,
preserved its tests, and ran both existing unittest cases successfully. This is
an unscored integration check, not a performance comparison or a general claim
about every Windows installation.

Earlier attempts with CLI `0.146.0` stalled in shell execution. Removing an
inherited desktop tool-routing variable did not fix that behavior. The newer
bundled CLI could edit files, but its test command initially failed because the
venv launcher could not start its base Python executable in user AppData. A
direct read-only sandbox command reproduced that interpreter launch failure.
The same Python version installed beneath the workspace passed the direct check
and the subsequent full repair. Sandbox permissions were not disabled or widened.
The evidence identifies a working setup; it does not establish the upstream
cause of either failure.

If a venv launcher reports `Unable to create process using ...python.exe`, check
which base interpreter it references in `pyvenv.cfg`. For this observed case,
these PowerShell commands prepare a workspace-local interpreter and environment:

```powershell
uv python install 3.12.11 --install-dir .ratchet-tools/python --no-bin --no-registry
uv venv .ratchet-tools/venv --python .ratchet-tools/python/cpython-3.12.11-windows-x86_64-none/python.exe
```

Install Ratchet and the project's test dependencies into that environment. From
a Ratchet source checkout, its own package and optional test/MCP dependencies are:

```powershell
uv pip install --python .ratchet-tools/venv/Scripts/python.exe ".[ratchet,mcp]"
& .ratchet-tools/venv/Scripts/ratchet.exe demo
```

In another project, install the versioned Ratchet wheel alongside that project's
dependencies, and add `.ratchet-tools/` and `.ratchet/` to its ignore rules. Supply
the full path of that environment's Python when asking Codex to run tests. Check
the actual CLI version with `codex --version`; a global npm command can differ
from the executable bundled with the desktop app. The tested alpha version is
reported as such, not described as a stable minimum version.

The plugin manifest invokes `ratchet mcp`, so its installed executable must be on
the PATH inherited by Codex. Configure a dedicated record directory first:

```powershell
New-Item -ItemType Directory -Force .ratchet
& .ratchet-tools/venv/Scripts/ratchet.exe configure --root .ratchet
```

The default plugin remains optional and read-only. The prospective experiment's
required-server startup setting is an explicit experimental configuration; do
not apply it silently to every Codex task. A required server may abort a worker
when startup fails. Provider failures after startup still preserve original
evidence and leave the comparison unresolved.

See the numeric receipts in `results/ratchet/`: `install-windows-expanded.json`,
`editing-preflight-windows-standalone.json`,
`editing-preflight-windows-desktop-cli.json`, and
`editing-preflight-windows-project-python.json`. Failed attempts remain present.
