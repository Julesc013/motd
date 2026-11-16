# Configuration

Recipes use TOML schema version 1. Start from `workshop`, `home-lab`, or `public-console`; omitted settings inherit that preset's defaults. Unknown keys are errors. The configurator writes supported settings back to TOML, but does not retain your original comments, spacing, or ordering.

```sh
python3 motd.py build --preset workshop --output ./workshop.bash --save-config ./workshop.toml
python3 motd.py preview --config ./workshop.toml
python3 motd.py build --config ./workshop.toml --output ./workshop.bash --replace
```

## A small recipe

```toml
schema_version = 1
preset = "home-lab"
name = "home-lab"
target = "shell"
audience = "ssh"
frequency = "login"
messages = ["Maintenance: check the backup report."]

[display]
title = "HOME LAB"
site = "Home"
theme = "green"
width = 100
rows = 25
top_entries = 3
sections = ["system", "resources", "services", "processes", "attention", "hints"]
show_swap = true
show_compression = true
show_pressure = true

[services]
required = ["ssh.service"]
exclude = []

[collection]
budget_ms = 140
worker_ms = 220
process_limit = 512
io_scan_ms = 35
journal = false
```

Use the service names actually installed on the host. `required` identifies expected units; `exclude` supplies service-name patterns. The workshop preset excludes `ollama*`, `llama*`, `vllm*`, and `lmstudio*`; home-lab does not inherit that exclusion list.

Installation scope, destination paths, shell startup file, and state directory are deployment arguments rather than TOML keys. Use `--scope`, `--destination`, `--shell-file`, and `--state-dir` when planning or installing.

## Supported settings

| Setting | Accepted values |
|---|---|
| `name` | 1–40 characters; starts with a lowercase letter, followed by lowercase letters, digits, or hyphens. |
| `target` | `shell`, `issue`, `ssh-banner`. |
| `audience` | `all`, `ssh`, `local`; filters eligible shell sessions. |
| `frequency` | `login`, `interactive`; shell display frequency. |
| `messages` | Up to 24 display-only strings. |
| `public_text` | Public static notice, including newlines; up to 16,000 characters. |
| `display.title`, `display.site` | Text, up to 100 characters each. |
| `display.theme` | `cyan`, `green`, `amber`, `mono`. |
| `display.width`, `display.rows` | Integers: width 40–240; row budget 20–60, with enough rows for the selected sections. |
| `display.top_entries` | Integer, 1–10. |
| `display.sections` | A nonempty list of distinct supported section IDs, in display order. |
| `display.show_swap`, `show_compression`, `show_pressure` | Boolean switches within `[display]`. |
| `services.required`, `services.exclude` | Arrays of service identifiers/patterns. |
| `collection.budget_ms`, `worker_ms` | Integer milliseconds: 20–5,000 and 50–10,000; worker budget must exceed collection budget. |
| `collection.process_limit`, `io_scan_ms` | Integers: process limit 32–65,536; I/O scan budget 5–1,000 milliseconds. |
| `collection.journal` | Boolean; journal collection defaults to `false`. |

Section IDs are `system`, `resources`, `services`, `processes`, `sessions`, `connections`, `attention`, `hints`, and `io`. The validator rejects a row budget too small for the selected sections and framing. Enabling a section does not grant access to unavailable system information. Collection budgets control intended work; they are not a measured wall-clock promise for every machine.

`frequency = "login"` requires Bash's login-shell flag. `"interactive"` also permits non-login interactive Bash sessions, such as many terminal windows, when they read the installed hook. Both require terminal output, honor `~/.hushlogin`, and suppress duplicate attachment within one shell process. User scope attaches to `.bashrc` and the active login file. The default system hook uses `/etc/profile.d`; extending it to non-login shells requires an explicit `--shell-file` read by those shells.

## Before/after commands

Hooks are optional executable calls, with an argv array, per-call timeout, and failure policy. For Fastfetch before the dashboard:

```toml
[[hooks.before]]
argv = ["fastfetch"]
timeout_seconds = 2
on_failure = "continue"
```

To run it after the dashboard instead, use `[[hooks.after]]`. Fastfetch must already be installed; the configurator does not install it. Each phase accepts up to 12 calls. A call defaults to a 1-second timeout and `on_failure = "continue"`; timeout values range from 0.05 to 60 seconds. `stop` ends the generated script at the failed hook, while `continue` proceeds.

Arguments do not acquire shell syntax automatically. If a command intentionally needs a pipeline, choose an explicit shell invocation:

```toml
[[hooks.after]]
argv = ["bash", "-c", "printf '%s\\n' 'Session ready' | tr '[:lower:]' '[:upper:]'"]
timeout_seconds = 1
on_failure = "continue"
```

Hook time is additional to the dashboard's collection budget. Both ordinary preview and `preview --live` suppress hooks. The `issue` and `ssh-banner` targets reject them.

## Hints and public text

Hints show commands for the human reader; they do not run them. Supplying `[[hints]]` records replaces the inherited hint list. Each requires a unique lowercase `id`, `label`, `command`, and `note`; the fields cannot contain `|`.

```toml
[[hints]]
id = "services"
label = "Services"
command = "systemctl --failed"
note = "List failed units"
```

Set `hints = []` at the top level to remove every hint. For public destinations, use `public_text` with the display title. Generated output is static text, with literal agetty backslashes escaped for the `issue` target. Imported static artifacts are already serialized bytes and are installed unchanged, including any existing escapes. Keep the recipe: public text outputs do not contain configuration metadata.
