# Shell outputs, login surfaces and visual configuration

Status: **v0.4 implementation contract and bounded extension plan**, 2026-11-17.
This extends the original v0.1 scope. Requirements describe acceptance behaviour;
they do not constitute a claim that every listed host has passed testing.
The [compatibility guide](../docs/compatibility.md) records primary-source reasons
for the version and attachment boundaries.

## 1. Preserve the small design

Keep one downloadable Python configurator, TOML recipes, a small set of embedded
canonical output templates, and one transaction engine. Add an output backend
when its interpreter requires different syntax. Reuse modern/portable Unix
dispatch through the Bash and Zsh entry points instead of maintaining a second
copy of all collectors for each shell major version. Fish delegates to the same
portable Unix payload; CMD launches the same native PowerShell core. Neither
wrapper adds a second collector implementation.

The configurator must import and generate outputs on Python 3.8+. It uses stdlib
`tomllib` on Python 3.11+ and licensed, ordinary embedded Tomli source on 3.8–3.10.
Generated output must not require Python, TOML or the source repository at login.

Separate these choices in the recipe and UI:

| Choice | Meaning |
|---|---|
| Action | Create, install, inspect, audit, repair, reconfigure, upgrade, recover, rollback or uninstall |
| Target | Interactive shell output, agetty issue text, OpenSSH banner text, generic UTF-8 text, or ASCII CMD batch notice |
| Shell | Bash with automatic fallback, Zsh or Fish launcher, native PowerShell, PowerShell-backed CMD launcher, or portable native sh output |
| Attachment | The exact startup file or public-text destination on the target machine |
| Display | Design, density, detail, spacing, priority, theme, section selection, geometry, messages and hints |

A transport such as SSH, Telnet or RDP is not an interpreter. Selecting one must
not silently select Bash, promise an unsupported server integration, or change
authentication settings.

## 2. Output requirements

1. Existing recipes without a shell selection retain Bash behaviour. Unknown
   enum values and unsupported settings produce an actionable error.
2. Generated outputs run independently of Python and the source tree. Their
   comments/help identify the actual interpreter and dependencies.
3. Zsh output declares its interpreter delegation: `/bin/bash` when present,
   otherwise `/bin/sh`. It must not describe itself as a native Zsh collector
   implementation. An inherited `ZSH_VERSION` must not create an exec loop.
4. Native sh output avoids Bash arrays, namerefs and Bash-only substitutions.
   The shared nine sections remain selectable. Unavailable data is not presented
   as zero, healthy, or measured. Old Bash executes this branch before parsing
   any later modern-Bash syntax. Bash 1 requires an available `printf` utility.
5. PowerShell output targets Windows PowerShell 1-era syntax through families
   1–5 and PowerShell 6–7, using feature checks and legacy API fallbacks.
   Host capability checks determine available collectors. A PS7/Linux test does
   not establish PS1–5/Windows compatibility. A modern-parser syntax check does
   not verify any historical engine. Emit configuration as data-only literals;
   do not depend on the later JSON cmdlet or advanced-function grammar.
6. Static outputs contain deliberate public content. They do not run hooks or
   collect private login telemetry. The `issue` encoder is agetty-specific;
   generic text has no claim of universal consumer escaping.
7. Arguments remain literal data unless the user explicitly invokes a shell.
   Before/after hooks have bounded execution and a visible failure policy.
   Previewing generated recipes never executes hooks.
8. A call that advertises a deadline must implement that deadline or report the
   capability unavailable, rather than silently executing it unbounded. Distinguish
   individual operation timeouts from whole-render time and descendant-process
   termination. State limitations in module initialization and kernel I/O.
9. Fish output forwards literal arguments to its embedded `/bin/sh` payload;
   test quotes, backslashes, dollar signs and command-looking text as data.
   Record required runtime libraries and matching data packages for relocated
   historical executables. Do not present an unavailable engine as a pass.
10. The CMD launcher stores visible PowerShell source after a batch exit marker,
    reads that exact file and forwards only understood runtime switches. It must
    not expand path metacharacters through a second shell evaluation. It requires
    an installed engine with `ScriptBlock.Create`; the wrapper is PS2+ until an
    actual PS1 method/engine check establishes a lower boundary.
11. `batch-text` is a separate static ASCII `cmd.exe` output. Escape literal CMD
    metacharacters, bound generated line lengths, reject ambiguous Unicode code
    pages, and require native Windows execution tests. Do not infer DOS or OS/2
    support from those tests.
12. The reserved `motd:print` hook action displays literal arguments as lines,
    sharing the before/after and demo-suppression rules. It must not start a shell,
    parse expressions or require a platform-specific executable. Its bounded data
    output is subject to ordinary terminal backpressure, not a child-process
    timeout. Imported arbitrary scripts are a separate trusted-execution path.

## 3. Shared presentation contract

All designs consume the same selected section observations and preserve their
units, unavailable states and scope. Presentation controls do not add collectors.
Unix renderers embed the canonical helper `runtime/designs.sh`; PowerShell keeps
the corresponding implementation in its single native core.

| Field | Accepted values and meaning |
|---|---|
| `design` | `classic` preserves the traditional frame; `cards` frames individual sections; `ledger` aligns unboxed rows; `briefing` puts attention headlines first; `dashboard` pairs cards in the configured section order at wide widths and stacks them at 40 columns. |
| `density` | `compact`, `balanced`, `comfortable`; alters spacing and ordinary detail allocation. |
| `detail` | `brief`, `normal`, `full`; controls desired section-row allocation within the available viewport. |
| `padding` / `section_gap` | Integer horizontal padding 0–3 and section gaps 0–2. |
| `priority` | Ordered section IDs controlling detail allocation and complete-section retention when space is short. |
| `section_detail` | Per-section `brief`, `normal` or `full` override. |
| `color_emphasis` | `quiet`, `balanced`, `vivid`; changes tone intensity while respecting plain/mono/NO_COLOR suppression. |

Runtime dimensions are 40–240 columns and 8–200 rows. Account for borders,
spacing, paired-card band heights, headings and omission notices before emitting
rows. Keep a prompt row free. A small viewport may omit whole lower-priority
sections; it must state that omission and retain complete frames. Wrap the full
names of hidden sections and budget every footer row; do not shorten away names
to pretend that more content fits. At 40×8 with many enabled sections, the context
and full hidden list can leave no room for a complete card. An empty
heading-only row cannot consume a briefing section's entire brief allocation:
promote the first actual detail when one exists. Preserve a visible DEMO label
for long titles; new presentation paths lead with it and retain host/uptime
context within the available geometry. Native PowerShell retains context even
when System is disabled. Legacy Unix classic defaults preserve their original
header placement; context can depend on an enabled System section and can be
reduced by the emergency short layout.
The classic frame retains its normal section allocation when every section's
minimum fits; short viewports use the shared omission planner.

## 4. Visual wizard requirements

The default on a suitable terminal is a page-by-page text interface, with
`--ui auto|screen|line` selecting its presentation. This is a terminal wizard;
it does not introduce a graphical desktop toolkit.

- Begin with the action. Show only choices relevant to that branch.
- Group target, interpreter, preset, appearance, sections and commands into
  readable stages. Permit changing an earlier choice before applying.
- Reserve exactly ten control rows: title, five questions, status, navigation,
  answer and preview label. Paginate additional choices. Place a clearly labelled
  synthetic preview in the remaining rows below the controls.
- Detect window resizing while awaiting input; preserve unfinished text and
  restore terminal flags after every answer, EOF, cancellation or error. Prefer
  actual terminal geometry over stale inherited COLUMNS/LINES values.
- Re-render for the available width and height rather than clipping a larger
  dashboard. Compact displays omit whole sections, retain borders and report
  omissions. The 40×25/50 and 80×25/50 windows have 15/40 preview rows.
- Hide configured before/after calls by default. An optional sample view shows
  before → MOTD → after with explicit synthetic labels; it must never execute
  those calls. Accept literal per-call preview_text for arbitrary programs and
  make unknown/omitted samples visible. Permit scrolling long sample sequences.
- Render previews from the selected output backend when it is available.
  If that interpreter is missing, explain the limit; a schematic must not be
  labelled as an executed native preview.
- Keep public static previews visually distinct from authenticated dashboards.
- Show what a choice changes, including reduced capabilities and required
  interpreters. Display long details on a separate page or in line mode.
- Retain explicit preview, plan, save recipe, build, install and cancel actions.
  No question-selection step modifies installed files.
- Fall back to a usable line interface for unsuitable terminals. Noninteractive
  automation uses the existing CLI instead of simulated keystrokes.
- Restore terminal state after cancellation or errors. Do not hide important
  installation plans behind a cleared screen before confirmation.

## 5. Installation and surface boundaries

All managed installation changes continue through the Linux journalled transaction
engine. Adding a renderer must not introduce an unrecorded profile-writing helper.
Create-only export is a separate cross-platform route: exclusively create new
UTF-8 files plus a content-hash manifest, refuse existing destinations and observed
symlink/reparse parents, and compensate only files still attributable to that
attempt. It creates no install state and makes no atomic multi-file claim.
Windows exports use this route by default; other hosts can select `--create-only`.
Replacement, managed Windows/macOS profiles and rollback require separate reviewed
filesystem/ownership/recovery implementations. Generation alone does not supply
those installers.

Current shell hooks must check interactive state, terminal suitability, configured
audience and duplicate invocation within a process. They must preserve unrelated
startup-file contents. Zsh must respect `ZDOTDIR`; PowerShell host integrations
must resolve that host's profile rather than guessing a common Windows path.
Do not change execution policy, enable services, install dependencies, reload
daemons, or edit authentication policy implicitly.

Future adapters are small, independently testable integrations:

| Adapter | Required contract before implementation is called supported |
|---|---|
| BusyBox getty/login/telnetd | Detect the actual applet/features, select the existing issue route, verify escaping and no duplicate display. |
| BSD getty | Review `gettytab` ownership and `%` expansion; generate a tested literal encoding. |
| PAM or distro update-motd | Identify the existing display/update route; do not replace the authentication stack or assume distro scripts are upstream PAM behaviour. |
| Windows PowerShell profile | Explicit host/scope selection, policy-respecting execution, Windows-safe transactions and uninstall. |
| RDP desktop-start display | Explicit opt-in to a visible terminal or notification after desktop login; distinguish reconnect from a new session. |
| Windows sign-in notice | Separate public title/text export and explicit local/domain policy ownership; no dashboard execution in the sign-in policy. |
| ksh and csh/tcsh startup attachment | Native startup rules and quoting tests; executing portable sh under ksh is not a tested installer for every ksh or csh profile. |
| Fish and CMD additional login surfaces | Existing generated wrappers retain their tested delegation boundaries; each new auto-start/login attachment still needs ownership and native-session tests. |
| DOS, OS/2 and early Windows | Explicit encoding/newline contract and native wrapper tests; static export is the starting point. |

Telnet support means content for an already configured service, not provisioning
that service. RDP support means an identified in-session or sign-in surface, not
an invented generic RDP text banner. PowerShell remoting, SFTP, remote command
execution and similar serialized transports must remain free of unsolicited
dashboard output.

## 6. Compatibility evidence and regression gates

Record the exact executable versions and OS for each result. Use three statuses:
verified, targeted but unverified, and specified for future implementation.
Do not use “all versions” or “all newer versions” as a test result.

| Boundary | Minimum useful evidence |
|---|---|
| Bash dispatch | Real historical major-family executions plus modern Bash; enhanced-renderer minimum-version checks; old engines exit before modern syntax and configured hooks still obey preview suppression |
| Zsh launcher | Actual Zsh invocation, correct argument forwarding, duplicate/interactive guards, and the shared Bash demonstration |
| Portable sh | At least dash plus a BusyBox ash build before claiming both; restricted environment and missing-utility behaviour |
| Fish | Actual Fish2.4, 3.6 and any additional claimed engine; literal payload/argument forwarding and truthful record of relocated runtime dependencies |
| PowerShell | Actual Windows PowerShell5.1, PS6 and PS7 checks; PS1, 3, 4 and 5.0 remain unexecuted targets; PS2 requires the separate exact-engine evidence below; OS-specific collector checks recorded separately |
| CMD launcher / batch notice | Actual `cmd.exe` execution on Windows; literal filename/text metacharacters, generated geometry, hook suppression and no-PowerShell static output |
| Python generation / export | Actual Python3.8 boundary, bundled-parser differential checks, new-file-only behavior, refusal of collisions, and preservation of externally edited files on failure |
| Hooks | Exactly-once calls, literal arguments, timeout/failure behaviour, and suppression during preview |
| Terminal wizard | Page navigation, updated preview, line fallback, cancellation, resize/narrow-terminal handling and no install before confirmation |
| New attachment | Temporary-file install/upgrade/uninstall/drift tests, followed by an isolated real host/session test before an end-to-end claim |

Keep normal verification small. Broaden the matrix when adding a declared
compatibility boundary or resolving a concrete regression. A missing optional
interpreter can skip a local test, but release evidence must name that skip.
Newer versions are candidates for the same checks; they are not automatically
certified by an open-ended version comparison.

`tools/test_legacy_powershell.ps1` must execute trusted generated files in the
actual requested engine, rejecting a major-version mismatch before any artifact
runs. Record exact engine, CLR, OS, bitness, automation assembly, artifact hashes,
four geometries, character modes and individual outcomes as XML usable on .NET2.
An optional live case uses local observations with hooks suppressed.

The dedicated PS2 CI job targets Windows Server2022, probes `-Version 2`, and may
enable only that disposable runner's available Windows optional components. It
does not provision a paid host, alter the user's machine or bypass execution
policy. If the component or real engine is unavailable, preserve the observed
blocking reason and skip the execution step explicitly. A green surrounding job
or a Windows PowerShell5.1 fallback cannot become PS2 evidence. Do not claim PS1,
PS3, PS4 or PS5.0 execution until a legitimate actual host has run the harness.

## 7. Reproducible PNG gallery

The maintained dashboard matrix is two presets × four output routes × four
themes × two character sets × two colour modes × four terminal sizes: **512
logical classic captures**. Three static public output formats add **12 captures**
at the same four sizes. The separate bounded design sampler contains **140
captures**: 120 structural comparisons (five designs × four sizes × two presets
× three native backends), 15 full-detail density contrasts, and five brief-detail
views. This is not the exhaustive Cartesian product of every control. Do not
invent colour/theme behavior for static notices or claim a native CMD image from
a Linux-only capture.

- Run the generated output in an actual controlling PTY set to 40×25, 40×50,
  80×25 or 80×50. Set runtime dimensions explicitly for reproducible captures;
  automatic geometry is tested separately without those flags.
- Use synthetic populated fixtures and suppress hooks. Retain raw ANSI bytes,
  effective TOML recipes, command lines, interpreter versions, and source hashes.
- Decode terminal cells and styles. Fail on unhandled sequences, wrapping,
  scrolling or overwriting the reserved prompt row. Do not crop overflow away.
- Preserve the full requested grid, including blank rows. Render high-resolution
  PNGs with a recorded font and cell geometry; contact sheets keep source pixels.
- Optimize PNGs losslessly and verify decoded RGBA hashes before and after.
  "100%" denotes preserved pixels, not a 100% byte reduction or a proof of the
  globally smallest possible compressed representation.
- Deduplicate identical pictures while retaining every logical case and its
  independent execution transcript. Provide a filterable local HTML index.
- CI verifies retained recipes, source/output/transcript/pixel hashes, dimensions
  and complete matrix coverage. A renderer change invalidates the old gallery;
  recapture before claiming that the images show the new revision.
