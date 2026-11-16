# Working on MOTD

Keep this project small: one Python configurator, canonical interpreter templates,
TOML recipes and generated standalone outputs. Zsh reuses the Bash renderer;
portable sh and PowerShell have explicit reduced native backends. Do not introduce
a daemon, plugin framework, package repository or duplicated collectors without
a concrete need.

## Ownership

- Edit configurator, validation, CLI and transaction code directly in `motd.py`.
- Edit templates in `runtime/`, then run `python3 tools/embed_runtime.py`.
- Do not hand-edit embedded literals or maintained examples separately.
- Update presets and regenerate examples with `python3 tools/build_examples.py`.
- Keep historical files in `reference/` unchanged; their timing evidence is historical.

## Behavior

- Parsing, planning and inspection must not execute imported outputs or hooks.
- Generated demo and live previews suppress configured calls. Exact imported
  code execution requires an explicit trusted live path and has no such guarantee.
- Every disk mutation to installed files goes through the transaction engine.
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

Run `python3 tools/embed_runtime.py --check`, `bash -n runtime/motd.bash`, and
`python3 -m unittest discover -s tests -v` for relevant changes. Tests use temporary
directories and guarded pseudo-terminal subprocesses; never install onto the
development host's real login files to validate behavior. Add a meaningful
regression test when correcting data, ownership or lifecycle behavior.

Run relevant native-shell parsing and execution tests for changed backends.
Record exact interpreter/OS versions and skips. A PowerShell7/Linux pass does not
prove Windows PowerShell5.1 behaviour; a portable-sh pass under dash does not
prove every BusyBox build or historical Bourne shell.

Record scope and uncertainty. A test in a container does not prove a real SSH,
agetty or systemd deployment. Do not describe journalled multi-file replacement
as an atomic transaction or claim preservation of metadata that is not implemented.
