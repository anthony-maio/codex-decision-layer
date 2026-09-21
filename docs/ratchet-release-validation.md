# Ratchet v0.1.1 patch validation

Status: operational checks passed for the experimental patch. Candidate v0.1.1-rc.2 is published and retained. Its installed Git-tag launcher failed offline restart on both platforms; the patch replaces tag resolution with an immutable package commit. The release's attached publication receipt records the final tag, CI run, and wheel hash. Existing tags are unchanged.

The candidate keeps Ratchet experimental and shadow-only. Classification failures block advisory promotion; workflow failures block savings and anti-thrashing claims. Operational safety, privacy, original recovery, or installation failures block release. These distinctions were declared in the [release plan](ratchet-plan.md) before scoring.

| Gate | Current evidence | Candidate status |
| --- | --- | --- |
| Windows/Linux unit and integration checks | Final candidate suite: 116 Windows passes, 114 Linux passes and two Windows-only skips | Passed locally |
| Isolated wheel install, reporter, CLI and saved-root MCP | Same candidate wheel passed expanded checks on both platforms | Passed locally |
| Offline replay, comparison and original recovery | Candidate passed with DNS/new connections denied after event-loop creation | Passed locally |
| Real Codex MCP and original retrieval | Fresh installed patch plugins on Windows/Linux; real CLI 0.146.0 status, comparison and exact original retrieval | Passed for recorded marketplace commit |
| Real code repair | Windows and Linux preflights passed; configurations differ and are documented | Passed within stated scope |
| Provider fail-open | Simulated timeout, connection, quota, server and malformed-response failures preserve evidence | Passed in candidate suite |
| Frozen classification | Combined precision 90.9%; one inherited critical false match | Failed; shadow only |
| Incremental Jev detection | Seven additional correct repeats, no added false matches | Passed on this holdout |
| Advisory eligibility | Two-attempt corpora cannot evaluate the declared warning policy | Not evaluated; disabled |
| Matched repair usefulness | All 45 workers retained; plain 15/15, deterministic 15/15, Jev 14/15 quality passes; both Ratchet methods slower than plain | Failed; no savings claim |
| Exact-commit hosted CI | Windows/Linux matrix passed for `c45e8e1`; final tag receipt is attached to the release | Passed for recorded commits |
| Privacy and artifact audit | Tracked-file scan and reviewed numeric artifacts contain no local keys, private absolute paths, raw sessions or handoffs | Passed within recorded scope |
| Versioned RC and installed patch | RC2 published and retained; corrected patch installed from immutable marketplace commit on both platforms | Corrected launcher passed online and offline |

The patch launcher uses uvx with immutable package commit `5491bef6eb8ed5992f3a0bec433bba624cd14a0c`, removing the requirement that an independently installed `ratchet` command be on Codex's PATH. That commit contains package version 0.1.1; the plugin manifests are committed afterward to avoid a self-referential commit hash. It still requires uv and Git. The product MCP server remains optional; the experiment's required-server startup amendment is not the product default.

The [RC2 failure receipt](../results/ratchet/installed-tag-rc2-failure.json) preserves both failed offline starts. The same caches launched successfully with the full package commit. A local wheel smoke had missed the Git-reference behavior, so the patch gate requires a fresh marketplace installation and the unmodified installed manifest on each platform.

To reproduce the installation check after publication, use `python scripts/validate_ratchet_install.py --repo . --private /path/outside/repository --ref v0.1.1 --version 0.1.1 --output ../installed-plugin-receipt.json`. The private directory must be new. This creates an isolated Codex home, copies the current user's local Codex authentication file into it, downloads into a fresh uv cache for the launcher smoke, checks an offline restart, and runs one real read-only Codex task. It uses the current sign-in and can consume model usage. For real Codex, it warms the default uv cache and temporarily configures the default saved Ratchet root, restoring the prior setting and backup afterward. Codex filters custom parent environment variables from MCP children. Credentials and raw sessions remain private; the output contains numeric fields, package versions, and hashes. The main Codex configuration is unchanged.

Patch receipts: [Windows wheel installation](../results/ratchet/install-windows-patch.json), [Linux wheel installation](../results/ratchet/install-linux-patch.json), [Windows installed Codex plugin](../results/ratchet/installed-patch-windows.json), and [Linux installed Codex plugin](../results/ratchet/installed-patch-linux.json). The wheel SHA-256 is `f6ef16516d7efb7432fad84beea23da4dcdf5818081dd17b1edd8f7c1f5b3d7c`. Wheel checks constrain dependencies with `uv.lock`; uvx resolves package metadata, and the installed receipts record actual dependency versions. Windows uvx used Python 3.13.7; Linux used 3.12.13. The direct launcher smoke checks both originals; each real Codex check retrieves the first original exactly. Package-manager offline checks and the separate Python DNS/connect-denial checks are distinct; no OS-wide network isolation is claimed.

The installed-plugin receipts bind marketplace commit `c45e8e18a98c51020bba285d4afd091d254b75a5` and package commit `5491bef6eb8ed5992f3a0bec433bba624cd14a0c`. Later receipt and documentation changes do not alter the package or manifests. The [unscored installation diagnostics](../results/ratchet/installed-patch-diagnostics.json) retain the failed environment-override probes and their usage separately from the frozen 45-run workflow. The corrected checks did not add a required-server override.

Hosted [Windows/Linux CI passed](https://github.com/anthony-maio/codex-decision-layer/actions/runs/35548607768) at `cca6aeeccd64bf7bc6e4750cbea4d93c9684b971`, including unit checks, MCP and meter transport, wheel build, and isolated installation. The first Windows run failed because a test compared an uncanonicalized root path with the canonical path used by the reader; an aliased-root reproduction confirmed the missed checkpoint. The test now targets the canonical directory, with no production reader change. Both the [failed attempt and correction](../results/ratchet/ci-windows-path-check.json) are retained.

The frozen holdout and workflow inputs remain attached to their original commits. Packaging this candidate does not replace their recorded hashes. Reproduce the workflow from its [declared commits](ratchet-workflow-reproduction.md).

The [completed repair report](ratchet-workflow-results.md) includes all per-task medians, cache-aware usage and cost bounds, selector overhead, the quality failure, and integration limitations. [Independent review](../results/ratchet/workflow-final-review.json) reproduced the public accounting and private evidence audits without rerunning or replacing any worker. Classification and workflow failures prohibit advisory/filtering promotion and savings claims; they do not become passing gates when packaging succeeds.

A release requires passing CI for its final commit, verified installation and original recovery, and privacy checks. Failed classification and usefulness gates remain explicit limitations, with all restricted behavior disabled.
