# Working on MOTD

Keep this project small: one Python configurator, canonical interpreter templates,
TOML recipes and generated standalone outputs. Bash and Zsh share automatic
modern/portable Unix dispatch and a shared `runtime/designs.sh` presentation engine; Fish launches the portable core and CMD launches the native PowerShell core.
Collection capabilities remain OS-specific. Do not introduce
a daemon, plugin framework, package repository or duplicated collectors without
a concrete need.

## Ownership

- Edit configurator, validation, CLI and transaction code directly in `motd.py`.
- Edit templates in `runtime/`, then run `python3 tools/embed_runtime.py`.
- Do not hand-edit embedded literals or maintained examples separately.
- Keep the Python 3.8 floor honest: test a real 3.8 interpreter, not only an AST grammar setting. The bundled TOML source and MIT provenance live in `vendor/tomli`; regenerate with `tools/embed_toml.py`.
- Update presets and regenerate examples with `python3 tools/build_examples.py`.
- Rebuild the terminal PNG gallery with `tools/build_gallery.py` after renderer
  changes; retain real PTY transcripts and reject wrap/scroll rather than crop it.
- Keep historical files in `reference/` unchanged; their timing evidence is historical.

## Behavior

- Parsing, planning and inspection must not execute imported outputs or hooks.
- Generated demo and live previews suppress configured calls. Exact imported
  code execution requires an explicit trusted live path and has no such guarantee.
- Every disk mutation to installed files goes through the transaction engine.
- Cross-platform create-only exports are a separate boundary: no overwrites or claimed journal recovery, hash manifest last, and only identity/content-checked compensation in trusted existing directories.
- Preserve unrelated startup-file text. Refuse drift inside owned blocks/files.
- Keep unavailable, partial and stale observations distinct from zero/healthy.
- Bash arithmetic settings require numeric validation before literal injection.
- Quote configuration for the actual output interpreter; Unix shlex is not a
  PowerShell quoting implementation. Keep unsupported metrics visibly unavailable.
- Wizard previews use synthetic data and suppress hooks; no page selection writes
  installation files. Keep line mode usable on limited terminals.
- No hidden privilege escalation, package installation, network calls at login,
  or service reloads. Before/after calls are explicit user configuration.

## Verification

Run `python3 tools/embed_runtime.py --check`, `python3 tools/embed_toml.py --check`, `bash -n runtime/motd.bash`, `sh -n runtime/designs.sh`, and
`python3 -m unittest discover -s tests -v` for relevant changes. Tests use temporary
directories and guarded pseudo-terminal subprocesses; never install onto the
development host's real login files to validate behavior. Add a meaningful
regression test when correcting data, ownership or lifecycle behavior.

Run relevant native-shell parsing and execution tests for changed backends.
Record exact interpreter/OS versions and skips. A PowerShell7/Linux pass does not
prove Windows PowerShell5.1 behaviour; a portable-sh pass under dash does not
prove every BusyBox build or historical Bourne shell.
PowerShell 1-era syntax is a target until tested with a real PowerShell 1 engine.
Do not label Bash or Zsh major families as Microsoft-style LTS releases. PNG
compression must preserve decoded pixels; high compression is not a promise of
the mathematically smallest possible PNG.

Record scope and uncertainty. A test in a container does not prove a real SSH,
agetty or systemd deployment. Do not describe journalled multi-file replacement
as an atomic transaction or claim preservation of metadata that is not implemented.
