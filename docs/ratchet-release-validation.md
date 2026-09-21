# Ratchet v0.1.1-rc.2 candidate validation

Status: preparation in progress. This version is not yet published. Existing tags are unchanged.

The candidate keeps Ratchet experimental and shadow-only. Classification failures block advisory promotion; workflow failures block savings and anti-thrashing claims. Operational safety, privacy, original recovery, or installation failures block release. These distinctions were declared in the [release plan](ratchet-plan.md) before scoring.

| Gate | Current evidence | Candidate status |
| --- | --- | --- |
| Windows/Linux unit and integration checks | Candidate: 113 Windows passes, 111 Linux passes and two Windows-only skips | Passed locally |
| Isolated wheel install, reporter, CLI and saved-root MCP | Same candidate wheel passed expanded checks on both platforms | Passed locally |
| Offline replay, comparison and original recovery | Candidate passed with DNS/new connections denied after event-loop creation | Passed locally |
| Real Codex MCP and original retrieval | Installed local development plugin verified | Published-tag check pending |
| Real code repair | Windows and Linux preflights passed; configurations differ and are documented | Passed within stated scope |
| Provider fail-open | Simulated timeout, connection, quota, server and malformed-response failures preserve evidence | Passed in candidate suite |
| Frozen classification | Combined precision 90.9%; one inherited critical false match | Failed; shadow only |
| Incremental Jev detection | Seven additional correct repeats, no added false matches | Passed on this holdout |
| Advisory eligibility | Two-attempt corpora cannot evaluate the declared warning policy | Not evaluated; disabled |
| Matched repair usefulness | 45-worker schedule in progress; retained method failures and startup amendment | Not established |
| Exact-commit hosted CI | Windows/Linux matrix passed for `cca6aee` | Preparatory candidate passed; final release commit pending |
| Privacy and artifact audit | Private files excluded during development | Final candidate audit pending |
| Versioned RC and published installation | Package and launcher target v0.1.1-rc.2 | Pending |

The new launcher uses uvx with a tagged package reference, removing the requirement that an independently installed `ratchet` command be on Codex's PATH. It still requires uv and Git. The product MCP server remains optional; the experiment's required-server startup amendment is not the product default.

Local receipts: [suite and manifests](../results/ratchet/candidate-local-validation.json), [Windows installation](../results/ratchet/install-windows-rc2.json), and [Linux installation](../results/ratchet/install-linux-rc2.json). The tested wheel SHA-256 is `608d845d7575d48878f304111c0ceb108f901d021172d0ae1eef49f07ba9a3a8`. Wheel checks constrain dependencies with `uv.lock`; the uvx launcher resolves dependencies from package metadata. The tagged-launcher test must record its actual environment separately.

Hosted [Windows/Linux CI passed](https://github.com/anthony-maio/codex-decision-layer/actions/runs/35548607768) at `cca6aeeccd64bf7bc6e4750cbea4d93c9684b971`, including unit checks, MCP and meter transport, wheel build, and isolated installation. The first Windows run failed because a test compared an uncanonicalized root path with the canonical path used by the reader; an aliased-root reproduction confirmed the missed checkpoint. The test now targets the canonical directory, with no production reader change. Both the [failed attempt and correction](../results/ratchet/ci-windows-path-check.json) are retained.

The frozen holdout and workflow inputs remain attached to their original commits. Packaging this candidate does not replace their recorded hashes. Reproduce the workflow from its [declared commits](ratchet-workflow-reproduction.md).

No patch release is authorized by this status table until its applicable operational gates pass. A completed experimental release may retain failed classification and usefulness gates only with these limitations documented and all restricted behavior disabled.
