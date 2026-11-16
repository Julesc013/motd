# Design: Python configures, Bash displays

## The boundary

The first version preserves the existing workshop engine and gives it a repeatable configuration, generation, and installation workflow. Python runs when someone creates or manages a display. Bash runs when the generated dashboard is shown. Static prelogin destinations receive text.

This removes the configurator from the login path without requiring a native-code rewrite. The source remains modular even though the user downloads one `motd.py` and can deploy one generated Bash file.

## Why Python 3.11

Python 3.11 includes `tomllib` in its standard library. It parses TOML into ordinary data structures, allowing human-readable presets without an additional installed package. It **does not write TOML**; the configurator writes its constrained schema and does not preserve existing TOML comments or formatting. [Python documentation](https://docs.python.org/3.11/library/tomllib.html)

| Configurator option | What it offers | Tradeoff for this project |
|---|---|---|
| **Python 3.11 standard library** | Structured configuration, file management, metadata, argument handling, and an interactive workflow in a readable single-file delivery. | The machine running the configurator needs Python 3.11+. This requirement does not transfer to generated Bash displays. |
| **Bash-only generator** | A familiar shell dependency and close proximity to the existing runtime. | Schema validation, metadata recovery, transaction records, quoting, and wizard state become shell code to maintain. It remains a possible small bootstrap, not a reason to duplicate the configurator. |
| **Go generator** | A compiled configurator can remove the user's Python prerequisite. Go supports multiple target operating systems and architectures. | Binary releases introduce a target/build matrix. Compilation does not by itself improve the emitted Bash dashboard. Reconsider if installing Python is a demonstrated deployment obstacle. |

The recommendation is an engineering judgment about development and deployment costs, not a claim that Python is universally faster or that Go cannot generate scripts. Go documents its supported `GOOS`/`GOARCH` combinations and build requirements in its [installation documentation](https://go.dev/doc/install/source#environment).

## One runtime, explicit configuration

`runtime/motd.bash` is the canonical runtime. Packaging embeds it verbatim in `motd.py`; generation supplies validated settings and wrapper behavior without maintaining another hand-edited engine. A runtime fix must reach every preset through that shared source.

Presets are TOML data. Configuration chooses supported values, sections, labels, and presentation. It is not sourced as shell code. Generated Bash metadata records the effective configuration and format version, so reconfiguration does not depend on reverse-engineering Bash assignments. Static public text has no metadata; its recipe remains a separate file or transaction archive.

`workshop`, `home-lab`, and `public-console` are starting configurations. The target (`shell`, `issue`, or `ssh-banner`), installation scope (`user` or `system`), and shell audience (`all`, `ssh`, or `local`) are explicit choices. They do not create independent copies of the engine. The unchanged historical workshop/home-lab scripts and their available documentation remain under `reference/` with provenance.

The existing engine remains responsible for collecting and displaying its supported metrics. This version does not add a generic plugin ABI, a layout language, or a second rendering engine. A new collector needs a concrete user need, defined units and missing-data behavior, and evidence that it does not degrade the normal display unexpectedly.

## Commands are explicit

Optional before/after commands use arrays of arguments. A value containing spaces is one argument when the configuration says it is one argument. Pipes, redirections, substitutions, and glob expressions do not acquire shell meaning merely because they appear in a string.

When shell syntax is wanted, the user chooses it explicitly, for example as the argument array `["bash", "-c", "printf '%s\\n' 'Ready'"]`. This remains executable user configuration, not a data-only theme. Both demonstration preview and `preview --live` suppress hooks for generated recipes. Recognized artifacts are regenerated for preview; explicitly running opaque code with `--live --trust-artifact` cannot suppress that code's side effects. Inspection never executes an imported script.

Python recommends argument sequences for subprocess calls. Its `shlex` quoting helpers target Unix shells and are not a portable Windows quoting layer. These boundaries support the deliberate Linux/Bash scope. [Subprocess documentation](https://docs.python.org/3.11/library/subprocess.html) · [shlex documentation](https://docs.python.org/3.11/library/shlex.html)

## Recovery and imports

Managed generation has two durable inputs: the effective configuration and the exact runtime version. Installation adds a record of paths and outputs. Recipe-based transactions archive `config.toml`, `output.bash` or `output.txt`, a journal, and binary before/after images. Opaque imports archive their exact output and fingerprint without inventing a recipe. User state lives under `${XDG_STATE_HOME:-$HOME/.local/state}/motd`; system state uses `/var/lib/motd-wizard`. `--state-dir` selects another state directory, including for isolated verification.

Recovery reverses an interrupted apply. Rollback creates an inverse transaction for a completed apply and rejects conflicting later ownership or file drift. Named installation repair uses the complete current manifest across upgrades, no-op changes, and rollback lineage; it restores only missing owned files and leaves modified files alone. Individual replacements are atomic; a change spanning multiple files is journaled, not atomic as a whole. Recovery preserves bytes, mode, UID, and GID, but does not preserve ACLs or extended attributes in v0.1. The project lock does not exclude other programs editing the same files.

Recognized generated metadata can recover settings, subject to validation. Arbitrary Bash can only be treated as an opaque trusted import. Its SHA-256 identifies bytes for comparison; it is not a signature, an approval, or a parser for the script's behavior. Inspection must not source or execute it.

Imported static artifacts are already serialized output and are installed unchanged. The configurator does not reinterpret or sanitize their existing consumer-specific escapes. Generated `issue` notices take a different input path: literal recipe text is escaped for agetty during generation.

## Performance and scope

Configurator startup and login display latency are different measurements. Optimize the runtime with the same enabled sections, output, and metric semantics when comparing changes. A faster result that drops a collector or substitutes a different metric is a different workload.

The initial design avoids a resident daemon, remote calls during normal display, automatic updates at login, and a separate graphical designer. Improve the existing runtime and the small management workflow first. The inherited dashboard uses Linux/procfs, Bash 4.3+, and GNU `timeout`; additional platforms require actual integration work and verification. Python's availability on a platform does not make the generated Bash dashboard supported there.
