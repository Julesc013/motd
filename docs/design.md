# Design: Python configures, standalone outputs display

## The boundary

Python runs when someone creates or manages a display. The selected interpreter
runs the generated output at login. Generated Bash and Zsh files select the
enhanced Linux/Bash renderer or the portable Unix renderer at invocation time.
PowerShell has a native template using PowerShell 1-era syntax and capability
checks. Fish launches the portable sh body; CMD launches an embedded PowerShell body. Public prelogin destinations receive static text, with an additional literal ASCII batch-notice target for Windows CMD.

The source remains reviewable while users download one `motd.py` and deploy one
generated file. Output compatibility and installation compatibility are separate:
the managed transaction engine still targets Linux. Windows and other hosts can generate outputs using the separate create-only exporter in a trusted directory.

## Why Python 3.8 and a bundled parser

Python 3.11 includes `tomllib`; Python 3.8–3.10 use the bundled, readable Tomli 2.3.2 source. Both parse TOML into ordinary data structures without an installed package dependency. The configurator writes its constrained schema and does not preserve original TOML comments or formatting. The vendored source, MIT licence and pinned archive hash are retained under `vendor/tomli`; `tools/embed_toml.py` assembles the one-file delivery without compressed code or runtime `exec`. [Python documentation](https://docs.python.org/3.11/library/tomllib.html) · [Tomli source](https://github.com/hukkin/tomli)

| Configurator option | What it offers | Tradeoff for this project |
|---|---|---|
| **Python 3.8+ single-file generator** | Structured validation, metadata, planning and a terminal wizard, with a bundled TOML parser where needed. | The generator needs Python 3.8+; generated outputs do not need Python. Supporting an old interpreter does not imply that its security maintenance is current. |
| **Bash-only generator** | A familiar shell dependency and close proximity to the existing runtime. | Schema validation, metadata recovery, transaction records, quoting, and wizard state become shell code to maintain. It remains a possible small bootstrap, not a reason to duplicate the configurator. |
| **Go generator** | A compiled configurator can remove the user's Python prerequisite. Go supports multiple target operating systems and architectures. | Binary releases introduce a target/build matrix. Compilation does not by itself improve the emitted Bash dashboard. Reconsider if installing Python is a demonstrated deployment obstacle. |

The recommendation is an engineering judgment about development and deployment costs, not a claim that Python is universally faster or that Go cannot generate scripts. Go documents its supported `GOOS`/`GOARCH` combinations and build requirements in its [installation documentation](https://go.dev/doc/install/source#environment).

Python 3.0 is not an implemented target. The current source uses later language and library features throughout: f-strings, pathlib, exception chaining and filesystem/process APIs are part of its maintainable implementation. Reaching 3.0 would require a separate compatibility rewrite and OS/runtime test matrix. The practical portability boundary is to run the generator on a supported modern machine and copy its standalone output to older systems. The audit records the actual 3.8 execution evidence and remaining host boundaries.

## Shared templates, explicit configuration

`runtime/` contains canonical templates for Bash, native sh and PowerShell, plus a shared POSIX presentation engine in `runtime/designs.sh`.
Packaging embeds them verbatim in `motd.py`; generation supplies validated settings
and wrapper behaviour. Zsh delegates through the available Unix interpreter, so
a renderer fix reaches both entry points. The portable body is parsed and can exit
before an old interpreter reaches modern Bash syntax. A preset does not receive
its own duplicated collectors. Bash and portable sh expose small adapters to the same presentation engine; the PowerShell equivalent follows the same contract in native syntax. Fish and CMD are launch adapters, not additional collector implementations.

## One content model, five structures

Configuration chooses a design (`classic`, `cards`, `ledger`, `briefing` or `dashboard`) separately from density, detail, padding, gaps, palette and emphasis. The planner works with section identity, preferred content rows, framing and a retention priority. It reduces optional detail before omitting complete low-priority sections, reports omissions by name, and reserves a prompt row. Density and the retained bands determine gaps; padding remains the requested inset. Display order and retention priority are separate choices, with briefing deliberately presenting enabled Attention first.

The original classic framing is retained for existing recipes. Cards separate topics; ledger removes most framing; briefing promotes summaries; dashboard pairs panels only when columns permit. These are presentations of the same backend observations. A colour or design switch must not silently change collection semantics, turn missing data into a healthy state, or run a command that was only shown as a hint.

The implementation has no arbitrary layout-language interpreter. A new design is a reviewed renderer over the existing model. This keeps historical shells viable and avoids asking users to debug another programming language.

Presets are TOML data. Configuration chooses values, sections, labels and
presentation; it is not sourced as shell code. Generated shell metadata records
the effective configuration and format version. Static text has no metadata;
its recipe remains a separate file or transaction archive.

`workshop`, `home-lab` and `public-console` are starting configurations. Target
(`shell`, `issue`, `ssh-banner`, `text`, `batch-text`), shell (`bash`, `zsh`, `sh`, `fish`, `powershell`, `cmd`),
installation scope and audience are distinct choices. Older schema1 recipes omit
`shell` and retain Bash. Historical scripts remain under `reference/` with provenance.

Each backend states its actual metrics and missing-data behaviour. The portable
and PowerShell backends implement the shared section model while using local OS
capabilities and explicit metric labels. Sharing configuration does not make
those measurements or timing guarantees equivalent. There is
no generic plugin ABI or layout language. A new collector needs a concrete user
need, defined units and evidence that it does not degrade the normal display.

## A live terminal wizard

The wizard is a terminal presentation over the same configuration and planning
functions as the CLI. Ten fixed control rows contain the question, answer and key hints; the remaining rows belong to the preview. It uses numbered choices, arrow selection, context help, grouped settings and generated synthetic previews. A line
presentation remains available through `--ui line`; no third-party TUI framework
is required. Previewing choices never installs them or executes configured hooks.
Terminal limitations and absent target interpreters remain visible.

The screen driver retains an unfinished answer during a resize and emits changed rows in one buffered update. Windows uses console input and an explicitly enabled/restored virtual-terminal mode when available; incapable consoles use line prompts. Preview caching avoids rerunning identical views, but a new interpreter process or changed configuration can still take time. Cold native PowerShell startup is an explicit remaining performance cost, not a zero-latency guarantee.

## Commands are explicit

Optional before/after commands use arrays of arguments. A value containing spaces is one argument when the configuration says it is one argument. Pipes, redirections, substitutions, and glob expressions do not acquire shell meaning merely because they appear in a string.

When shell syntax is wanted, the user chooses it explicitly, for example as the argument array `["bash", "-c", "printf '%s\\n' 'Ready'"]`. This remains executable user configuration, not a data-only theme. Both demonstration preview and `preview --live` suppress hooks for generated recipes. Recognized artifacts are regenerated for preview; explicitly running opaque code with `--live --trust-artifact` cannot suppress that code's side effects. Inspection never executes an imported script.

The reserved `motd:print` operation writes literal configured lines without launching a process. Preview-only samples of Fastfetch or other calls remain separate metadata. Showing a sample never invokes the call, and samples are hidden by default.

Python recommends argument sequences for subprocess calls. Its `shlex` helpers
target Unix shells, so PowerShell generation uses its own literal encoding and
execution path. Never reuse shell quoting based solely on a filename extension.
[Subprocess documentation](https://docs.python.org/3.11/library/subprocess.html) ·
[shlex documentation](https://docs.python.org/3.11/library/shlex.html)

## Recovery and imports

Managed generation has two durable inputs: effective configuration and exact
runtime version. Installation adds paths and outputs. Archives contain
`config.toml` when available, the generated output, a journal and binary
before/after images. Opaque imports retain exact output and a fingerprint without
an invented recipe. User state is `${XDG_STATE_HOME:-$HOME/.local/state}/motd`;
system state is `/var/lib/motd-wizard`. `--state-dir` supports isolated verification.

Recovery reverses an interrupted apply. Rollback inverses a completed apply and
rejects conflicting ownership or drift. Named repair uses the complete current
manifest across upgrades and rollback lineage; it restores missing owned files
and preserves modified ones. Individual replacements are atomic; a multi-file
change is journalled. Bytes, mode, UID and GID are preserved; ACLs and extended
attributes are not. The project lock cannot exclude noncooperating writers.

Recognized generated metadata can recover settings, subject to validation.
Arbitrary scripts are opaque imports. Their SHA-256 identifies bytes for
comparison; it is not a signature, an approval or a behaviour parser. Inspection
must not source or execute them.

The separate cross-platform exporter only creates new files in existing trusted directories. It writes a hash manifest last and compensates an ordinary failed write only when the newly created file still has the expected identity and content. It never overwrites a destination and does not claim the Linux journal's crash recovery or pinned-directory protections. Source reads are bounded to 2 MB and transaction snapshots to 16 MiB per file; paths containing terminal controls are refused before writes.

Imported static artifacts are already serialized output and are installed unchanged. The configurator does not reinterpret or sanitize their existing consumer-specific escapes. Generated `issue` notices take a different input path: literal recipe text is escaped for agetty during generation.

## Performance and scope

Configurator startup and login display latency are different measurements. Optimize the runtime with the same enabled sections, output, and metric semantics when comparing changes. A faster result that drops a collector or substitutes a different metric is a different workload.

The design needs no resident daemon, remote calls during normal display,
automatic updates at login or separate graphical designer. The inherited Bash
dashboard uses Linux/procfs, Bash 4.3+ and GNU `timeout`. Each additional backend
and attachment needs its own capability and version evidence. The
[compatibility specification](../specs/compatibility.md) defines that boundary
without turning every possible platform into a prerequisite for this version.

## Evidence-based previews

The developer gallery runs generated artifacts in controlling pseudo-terminals
at each requested geometry. A strict cell decoder rejects wrapping, scrolling,
unsupported escape sequences and output that consumes the prompt row. It does
not delete inconvenient output to make a screenshot fit. Rendering preserves
the entire grid, including unused rows. Lossless PNG optimization is accepted
only when decoded RGBA pixels match before and after optimization.

Synthetic fixtures make comparisons reproducible without publishing host data.
Each logical case retains its transcript, effective recipe, command, engine
version and source hashes even when identical pictures share a PNG. Gallery-only
Pillow, wcwidth and optional oxipng dependencies are absent from normal generation
and login execution.
