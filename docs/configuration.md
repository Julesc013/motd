# Configuration

Recipes use TOML schema version 1. Start from `workshop`, `home-lab`, or `public-console`; omitted settings inherit that preset's defaults. The additive `shell` setting defaults to `bash`, so older recipes retain their interpreter. Unknown keys are errors. The configurator writes supported settings back to TOML, but does not retain your original comments, spacing, or ordering.

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
shell = "bash"
audience = "ssh"
frequency = "login"
messages = ["Maintenance: check the backup report."]

[display]
title = "HOME LAB"
site = "Home"
theme = "green"
charset = "auto"
color = "auto"
design = "cards"
density = "comfortable"
detail = "normal"
padding = 1
section_gap = 1
color_emphasis = "balanced"
bar_layout = "wide"
width = 100
rows = 25
top_entries = 3
sections = ["system", "resources", "services", "processes", "attention", "hints"]
priority = ["attention", "resources", "system", "services", "processes", "hints"]
section_detail = {resources = "full", processes = "brief"}
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
| `target` | `shell`, `issue`, `ssh-banner`, `text`, `batch-text`. |
| `shell` | `bash` (default), `zsh`, `sh`, `fish`, `powershell`, `cmd`; selects executable syntax when `target = "shell"`. |
| `audience` | `all`, `ssh`, `local`; filters eligible shell sessions. |
| `frequency` | `login`, `interactive`; shell display frequency. |
| `messages` | Up to 24 display-only strings. |
| `public_text` | Public static notice, including newlines; up to 16,000 characters. Native `batch-text` requires ASCII here and in `display.title`; validation preserves the prior wizard draft on an invalid edit. |
| `display.title`, `display.site` | Text, up to 100 characters each. |
| `display.theme` | `cyan`, `green`, `amber`, `mono`. |
| `display.charset` | `auto` (default), `ascii`, `unicode`; a saved default that runtime switches may override. |
| `display.color` | `auto` (default), `always`, `never`; `NO_COLOR` and the mono theme still disable colour. |
| `display.design` | `classic` (default), `cards`, `ledger`, `briefing`, `dashboard`. Changes the structure, independently of palette. |
| `display.density` | `compact`, `balanced` (default), `comfortable`; the spacing and row-allocation preference. |
| `display.detail` | `brief`, `normal` (default), `full`; how much content to request when space permits. |
| `display.padding` | Integer 0–3; horizontal inset within the chosen design. |
| `display.section_gap` | Integer 0–2; blank-row preference between section bands, adjusted by density. Fewer retained bands need fewer gaps. |
| `display.color_emphasis` | `quiet`, `balanced` (default), `vivid`; colour emphasis within the chosen palette. |
| `display.bar_layout` | `inline` (default), `wide`; wide puts the numeric label and its gauge on separate rows, filling the current panel width. |
| `display.width`, `display.rows` | Integers: width 40–240; total terminal row budget 8–200, including the reserved prompt row. |
| `display.top_entries` | Integer, 1–10. |
| `display.sections` | A nonempty list of distinct supported section IDs, in display order. |
| `display.priority` | Up to nine distinct section IDs, most protected first. Unlisted enabled sections follow in display order. This does not reorder the display. |
| `display.section_detail` | Inline table or TOML subtable mapping section IDs to `brief`, `normal`, or `full`. Overrides the overall detail preference for those sections. |
| `display.show_swap`, `show_compression`, `show_pressure` | Boolean switches within `[display]`. |
| `services.required`, `services.exclude` | Arrays of service identifiers/patterns. |
| `collection.budget_ms`, `worker_ms` | Integer milliseconds: 20–5,000 and 50–10,000; worker budget must exceed collection budget. |
| `collection.process_limit`, `io_scan_ms` | Integers: process limit 32–65,536; I/O scan budget 5–1,000 milliseconds. |
| `collection.journal` | Boolean; journal collection defaults to `false`. |

Section IDs are `system`, `resources`, `services`, `processes`, `sessions`, `connections`, `attention`, `hints`, and `io`. The layout reduces optional detail, then omits complete lower-priority sections if needed. Density and the retained section bands determine spacing; requested gaps are generally retained, with an emergency minimum layout for extremely short viewports. A named `Hidden:` footer makes omissions visible. Enabling a section does not grant access to unavailable system information. Hidden sections may still share collection work or feed warnings; section selection is not a promise to disable every associated system query.

### Wide resource bars

`--bar-layout wide` uses a label/value row followed by a gauge spanning the
current panel's content width. It reuses collected observations and makes no
additional system query. A dashboard gauge fills its card, not neighbouring
cards. Under row pressure, numeric labels survive before their optional gauges;
whole lower-priority sections can still be omitted.

Read the quantity named in each label. Enhanced Bash shows RAM used as
`total - available` and aggregate storage used; this differs from its classic
physical-allocation segmented bar. Portable sh shows RAM available (or explicitly
free when available is unknown), swap free, and the root filesystem percentage
reported by `df`. PowerShell uses its observed used/total readings. These provider
differences remain explicit; a design does not redefine a metric. Unknown or
invalid fractions do not become zero-filled healthy bars.

Generated Unix outputs accept `--bar-layout inline|wide`; native PowerShell
accepts `-BarLayout inline|wide`. Omitting the setting keeps the existing inline
appearance. See the [retained comparisons](../gallery/bars/README.md).

## Choose a structure, then tune it

| Design | Presentation | Useful starting point |
|---|---|---|
| `classic` | The original compact framed dashboard. | Existing recipes and familiar operational views. |
| `cards` | Separate, strongly labelled section cards. | More separation between kinds of information. |
| `ledger` | Open aligned rows with restrained framing. | Scanning values and comparing adjacent facts. |
| `briefing` | Section summaries followed by requested detail. | A readable arrival message with an overview. |
| `dashboard` | Paired panels when wide, stacked panels when narrow. | Using extra columns without forcing a wide terminal. |

The same collectors supply all five. Density, detail, padding, section gap and colour are independent preferences, subject to the terminal budget. `comfortable` plus `brief` requests more breathing room around fewer facts; `compact` plus `full` requests more facts in less space. No setting overrides the prompt-row reserve. The legacy recipe defaults retain the classic design; changing a design does not change which services are checked. Briefing presents an enabled Attention section first; the other designs retain display order. Custom retention priorities can omit Attention in a short viewport, so keep it first when warning visibility is your preference.

For example:

```sh
python3 motd.py build --preset workshop --design cards --density comfortable \
  --detail normal --padding 2 --section-gap 1 --color-emphasis quiet \
  --sections system,resources,services,attention,hints \
  --priority attention,resources,system --section-detail resources=full \
  --width 80 --rows 50 --output ./workshop-cards.bash
```

The same display switches are accepted when building from a recipe. To change an imported generated artifact, recover its recipe with `config` and rebuild it; changing metadata cannot safely relabel arbitrary executable bytes.

The full collection settings describe the enhanced Linux/Bash renderer (also
selected by Zsh where available). The portable Unix and PowerShell renderers use
the same section IDs and their own OS collectors, with unavailable observations
labelled explicitly. They do not turn Bash's `worker_ms` setting into an equivalent global
deadline. Collection settings are not a measured wall-clock promise for every
machine. See [coverage and dependencies](compatibility.md).

`frequency = "login"` selects login-shell attachment; `"interactive"` also permits
eligible non-login shells that read the chosen startup file. Bash and Zsh use their
native login-state tests where available; Bash1 uses its leading-`-` login
invocation convention. Portable sh relies on its selected login profile and
does not claim a universal non-login rc-file route. Hooks check interactive state,
terminal output, `~/.hushlogin` and duplicate invocation. `audience = "local"`
means no SSH environment marker was found, not proven physical-console access.
See [installation](install.md) for startup paths and PowerShell's manual boundary.

Fish uses a small native launcher around the same portable `/bin/sh` body. It needs that interpreter, and its embedded command payload is limited to 96,000 bytes to keep ordinary `exec` argument limits bounded. Select a direct sh output for a larger recipe. CMD output is a `.cmd` launcher containing the native PowerShell renderer; it needs PowerShell with `ScriptBlock.Create` support (PowerShell 2+ is the target). It prefers the installed Windows PowerShell path and otherwise invokes `pwsh.exe`. It does not make a PowerShell-dependent dashboard work on a machine without PowerShell.

## Before/after commands

Hooks are optional executable calls, with an argv array, per-call timeout, and failure policy. For Fastfetch before the dashboard:

```toml
[[hooks.before]]
argv = ["fastfetch"]
timeout_seconds = 2
on_failure = "continue"
```

To run it after the dashboard instead, use `[[hooks.after]]`. Fastfetch must already be installed; the configurator does not install it. Each phase accepts up to 12 calls. A call defaults to a 1-second timeout and `on_failure = "continue"`; timeout values range from 0.05 to 60 seconds. `stop` ends the generated script at the failed hook, while `continue` proceeds.

For literal text without a shell, subprocess or quoting puzzle, use the reserved `motd:print` call. Each argument after the name becomes one line, and preview samples use the same literal text:

```toml
[[hooks.after]]
argv = ["motd:print", "Session ready.", "Remember to check the backup report."]
```

This built-in operation does not interpret substitutions or command syntax. Its writes follow normal terminal/output backpressure; the subprocess timeout field is not an independent deadline for a blocked output stream.

Arguments do not acquire shell syntax automatically. If a command intentionally needs a pipeline, choose an explicit shell invocation:

```toml
[[hooks.after]]
argv = ["bash", "-c", "printf '%s\\n' 'Session ready' | tr '[:lower:]' '[:upper:]'"]
timeout_seconds = 1
on_failure = "continue"
```

Hook time is additional to display collection time. Both ordinary preview and
`preview --live` suppress hooks for generated recipes. All static targets reject
them. Native sh needs a GNU-compatible `timeout` for executable hooks; literal `motd:print` calls and its base
display does not need that utility. PowerShell hooks launch executable programs
or explicit interpreters: a bare PowerShell cmdlet is not an external executable.
Windows PowerShell 1–5 can terminate the direct hook process but do not provide
the same descendant-tree kill operation as current PowerShell/.NET. Avoid treating
these hook limits as a sandbox or a hard deadline for arbitrary descendant trees.

### Previewing before/after output

Wizard previews hide configured calls by default. Type `H` and Enter on a page
to include their **samples**, in before → MOTD → after order. This does not change
the recipe or run the commands. `J`/`K` scroll sample output that is longer than
the viewport. A representative Fastfetch sample and simple literal echo/printf
samples are built in; their output is illustrative, not a host observation.

For any program, save explicit sample text alongside its call:

```toml
[[hooks.before]]
argv = ["fastfetch"]
timeout_seconds = 2
on_failure = "continue"

[[hooks.after]]
argv = ["/usr/local/bin/workshop-notice"]
timeout_seconds = 1
on_failure = "continue"
preview_text = "Bench 3: drive testing in progress.\nSession ready."
```

`preview_text` accepts up to 4,000 characters including newlines, with no terminal
control sequences. It is display-only metadata; the installed runtime does not
print it instead of calling the configured command. An unknown call without a
sample is labelled explicitly. The add-call wizard asks for this optional text;
use `\\n` between lines in its answer. Shell expressions such as `bash -c ...`
are not interpreted to guess their output.

The wizard reserves ten control rows and gives the remaining rows to
the renderer. Its temporary preview overrides do not modify `display.width` or
`display.rows`. The terminal is measured again while an answer is pending,
including when inherited `COLUMNS`/`LINES` values are stale. A 25-row terminal
has a 15-row preview; a 50-row terminal has a 40-row preview.

Numbered choices and Up/Down with Enter are both available. `?` explains the current question; the footer shows navigation, sample and scrolling keys. The line interface explains choices without requiring ANSI cursor control. The screen interface redraws changed rows in a buffered update, retains an unfinished answer during resizing, and falls back to line mode when the terminal cannot support it. A first preview still has to start its selected interpreter; cold PowerShell startup can be noticeable.

## Runtime display switches

Unix outputs accept `--width 40 --rows 25`, `--ascii` / `--unicode`,
`--plain` / `--color`, and `--demo` / `--demo-alerts`. All Unix routes accept the
same explicit colour switches. Native PowerShell uses
`-Width 40 -Rows 25`, `-Ascii` / `-Unicode`, `-Color` / `-Plain`, and
`-Demo` / `-DemoAlerts`. The terminal can supply dimensions automatically;
explicit switches make examples and tests reproducible. `NO_COLOR`, including
an empty value, suppresses colours. Demo modes suppress hooks.

The presentation switches also work on generated output: Unix uses `--design cards --density compact --detail brief --padding 0 --section-gap 0 --color-emphasis quiet`; PowerShell uses `-Design cards -Density compact -Detail brief -Padding 0 -SectionGap 0 -ColorEmphasis quiet`. A CMD launcher forwards the PowerShell switches. Section selection, priority and individual detail preferences are recipe settings; rebuild to change them.

Runtime overrides and saved recipes both accept **8–200** rows. Temporary preview geometry does not change the saved configuration.
Saved character-set/colour choices are defaults, explicit switches can override
them, and plain mode, `NO_COLOR` and a mono theme retain colour-suppression precedence.

The layout reserves a row for the next shell prompt. Narrow displays shorten
values; taller displays can allocate more rows to enabled sections. ASCII mode
uses ASCII framing. Historical byte-oriented Unix paths normalize unsupported
text rather than pretending they implement complete Unicode terminal-cell widths.

## Hints and public text

Hints show commands for the human reader; they do not run them. Supplying `[[hints]]` records replaces the inherited hint list. Each requires a unique lowercase `id`, `label`, `command`, and `note`; the fields cannot contain `|`.

```toml
[[hints]]
id = "services"
label = "Services"
command = "systemctl --failed"
note = "List failed units"
```

Set `hints = []` at the top level to remove every hint. PowerShell's built-in hints
use `Get-Process`, `Get-Service` and `Get-PSDrive`. Changing the shell in the CLI or
wizard adapts an untouched built-in hint set; customized hints remain unchanged.
Custom hints and executable hooks are not translated between operating systems.
Review their commands when changing the destination.

For public destinations, use `public_text` with the display title. Generated output
is static text, with literal agetty backslashes escaped for `issue`; `ssh-banner`
and generic `text` preserve literal text without agetty conversion. Generic text
does not promise another getty's escaping, code page or newline convention.
Imported static artifacts are already serialized bytes and are installed
unchanged, including existing escapes. Keep the recipe: static outputs do not
contain configuration metadata.

`batch-text` emits an ASCII `.cmd` notice using literal escaped `echo` lines, without PowerShell, collectors or hooks. It targets the Windows NT CMD command processor, not DOS `COMMAND.COM`. Unicode notices should use `text` with a known consumer or the PowerShell backend. The notice is wrapped to its configured column width; it does not dynamically collect or rearrange system information.

## Create-only exports on Windows and other hosts

Builds on Windows use the create-only exporter, also available elsewhere with `--create-only`. It writes new output/recipe files and a final `.export.json` hash manifest in existing directories. Existing files are refused; use a new destination name for a revision. An ordinary failed write removes only newly created files whose identity and content still match this attempt. Changed files are preserved for review.

This exporter is separate from Linux managed installation. It has no overwrite journal, crash recovery, ACL restoration or guarantee against an attacker changing parent directories concurrently. Use a directory you control. Generation and recipe recovery accept regular UTF-8 source files up to 2 MB; path names containing terminal controls or newlines are rejected.
