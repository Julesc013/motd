# Design: Python configures, standalone outputs display

## The boundary

Python runs when someone creates or manages a display. The selected interpreter
runs the generated output at login. Bash remains the full workshop renderer;
Zsh launches that shared renderer, while portable sh and PowerShell have smaller
native templates. Public prelogin destinations receive static text.

The source remains reviewable while users download one `motd.py` and deploy one
generated file. Output compatibility and installation compatibility are separate:
the transaction engine still targets Linux.

## Why Python 3.11

Python 3.11 includes `tomllib` in its standard library. It parses TOML into ordinary data structures, allowing human-readable presets without an additional installed package. It **does not write TOML**; the configurator writes its constrained schema and does not preserve existing TOML comments or formatting. [Python documentation](https://docs.python.org/3.11/library/tomllib.html)

| Configurator option | What it offers | Tradeoff for this project |
|---|---|---|
| **Python 3.11 standard library** | Structured configuration, file management, metadata, argument handling, and an interactive workflow in a readable single-file delivery. | The machine running the configurator needs Python 3.11+. This requirement does not transfer to generated Bash displays. |
| **Bash-only generator** | A familiar shell dependency and close proximity to the existing runtime. | Schema validation, metadata recovery, transaction records, quoting, and wizard state become shell code to maintain. It remains a possible small bootstrap, not a reason to duplicate the configurator. |
| **Go generator** | A compiled configurator can remove the user's Python prerequisite. Go supports multiple target operating systems and architectures. | Binary releases introduce a target/build matrix. Compilation does not by itself improve the emitted Bash dashboard. Reconsider if installing Python is a demonstrated deployment obstacle. |

The recommendation is an engineering judgment about development and deployment costs, not a claim that Python is universally faster or that Go cannot generate scripts. Go documents its supported `GOOS`/`GOARCH` combinations and build requirements in its [installation documentation](https://go.dev/doc/install/source#environment).

## Shared templates, explicit configuration

`runtime/` contains canonical templates for Bash, native sh and PowerShell.
Packaging embeds them verbatim in `motd.py`; generation supplies validated settings
and wrapper behaviour. Zsh uses the Bash body, so a full-dashboard fix reaches both
routes. A preset does not receive its own duplicated collectors.

Presets are TOML data. Configuration chooses values, sections, labels and
presentation; it is not sourced as shell code. Generated shell metadata records
the effective configuration and format version. Static text has no metadata;
its recipe remains a separate file or transaction archive.

`workshop`, `home-lab` and `public-console` are starting configurations. Target
(`shell`, `issue`, `ssh-banner`, `text`), shell (`bash`, `zsh`, `sh`, `powershell`),
installation scope and audience are distinct choices. Older schema1 recipes omit
`shell` and retain Bash. Historical scripts remain under `reference/` with provenance.

Each backend states its actual metrics and missing-data behaviour. Portable sh
is deliberately reduced; native PowerShell uses its own OS capabilities and metric
labels. Sharing configuration does not make those collectors equivalent. There is
no generic plugin ABI or layout language. A new collector needs a concrete user
need, defined units and evidence that it does not degrade the normal display.

## A small visual wizard

The wizard is a terminal presentation over the same configuration and planning
functions as the CLI. It uses successive ANSI screens on compatible terminals,
numbered choices, grouped settings and generated synthetic previews. A line
presentation remains available through `--ui line`; no third-party TUI framework
is required. Previewing choices never installs them or executes configured hooks.
Terminal limitations and absent target interpreters remain visible.

## Commands are explicit

Optional before/after commands use arrays of arguments. A value containing spaces is one argument when the configuration says it is one argument. Pipes, redirections, substitutions, and glob expressions do not acquire shell meaning merely because they appear in a string.

When shell syntax is wanted, the user chooses it explicitly, for example as the argument array `["bash", "-c", "printf '%s\\n' 'Ready'"]`. This remains executable user configuration, not a data-only theme. Both demonstration preview and `preview --live` suppress hooks for generated recipes. Recognized artifacts are regenerated for preview; explicitly running opaque code with `--live --trust-artifact` cannot suppress that code's side effects. Inspection never executes an imported script.

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

Imported static artifacts are already serialized output and are installed unchanged. The configurator does not reinterpret or sanitize their existing consumer-specific escapes. Generated `issue` notices take a different input path: literal recipe text is escaped for agetty during generation.

## Performance and scope

Configurator startup and login display latency are different measurements. Optimize the runtime with the same enabled sections, output, and metric semantics when comparing changes. A faster result that drops a collector or substitutes a different metric is a different workload.

The design needs no resident daemon, remote calls during normal display,
automatic updates at login or separate graphical designer. The inherited Bash
dashboard uses Linux/procfs, Bash 4.3+ and GNU `timeout`. Each additional backend
and attachment needs its own capability and version evidence. The
[compatibility specification](../specs/compatibility.md) defines that boundary
without turning every possible platform into a prerequisite for this version.
