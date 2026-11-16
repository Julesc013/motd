# Shell outputs, login surfaces and visual configuration

Status: **implementation contract and bounded extension plan**, 2026-11-16.
This extends the original v0.1 scope. Requirements describe acceptance behaviour;
they do not constitute a claim that every listed host has passed testing.
The [compatibility guide](../docs/compatibility.md) records primary-source reasons
for the version and attachment boundaries.

## 1. Preserve the small design

Keep one downloadable Python configurator, TOML recipes, a small set of embedded
canonical output templates, and one transaction engine. Add an output backend
when its interpreter requires different syntax. Reuse modern/portable Unix
dispatch through the Bash and Zsh entry points instead of maintaining a second
copy of all collectors for each shell major version.

Separate these choices in the recipe and UI:

| Choice | Meaning |
|---|---|
| Action | Create, install, inspect, audit, repair, reconfigure, upgrade, recover, rollback or uninstall |
| Target | Interactive shell output, agetty issue text, OpenSSH banner text, or generic static text |
| Shell | Bash with automatic fallback, Zsh launcher, native PowerShell, or portable native sh output |
| Attachment | The exact startup file or public-text destination on the target machine |
| Display | Theme, section selection, geometry, messages and hints |

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

## 3. Visual wizard requirements

The default on a suitable terminal is a page-by-page text interface, with
`--ui auto|screen|line` selecting its presentation. This is a terminal wizard;
it does not introduce a graphical desktop toolkit.

- Begin with the action. Show only choices relevant to that branch.
- Group target, interpreter, preset, appearance, sections and commands into
  readable stages. Permit changing an earlier choice before applying.
- Show a clearly labelled synthetic preview beside or above the relevant
  appearance choices. Theme and section changes update the displayed result.
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

## 4. Installation and surface boundaries

All managed changes continue through the existing journalled transaction engine.
Adding a renderer must not introduce an unrecorded profile-writing helper.
Windows installation needs a separate reviewed implementation of filesystem,
ownership and recovery semantics before the Linux engine can claim that support.

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
| Fish, ksh, csh/tcsh, cmd.exe | Native startup rules and quoting tests; a file extension alone is not a backend. |
| DOS, OS/2 and early Windows | Explicit encoding/newline contract and native wrapper tests; static export is the starting point. |

Telnet support means content for an already configured service, not provisioning
that service. RDP support means an identified in-session or sign-in surface, not
an invented generic RDP text banner. PowerShell remoting, SFTP, remote command
execution and similar serialized transports must remain free of unsolicited
dashboard output.

## 5. Compatibility evidence and regression gates

Record the exact executable versions and OS for each result. Use three statuses:
verified, targeted but unverified, and specified for future implementation.
Do not use “all versions” or “all newer versions” as a test result.

| Boundary | Minimum useful evidence |
|---|---|
| Bash dispatch | Real historical major-family executions plus modern Bash; enhanced-renderer minimum-version checks; old engines exit before modern syntax and configured hooks still obey preview suppression |
| Zsh launcher | Actual Zsh invocation, correct argument forwarding, duplicate/interactive guards, and the shared Bash demonstration |
| Portable sh | At least dash plus a BusyBox ash build before claiming both; restricted environment and missing-utility behaviour |
| PowerShell | Actual Windows PowerShell5.1, PS6 and PS7 checks; PS1–4 retain targeted status until their real engines execute the tests; OS-specific collector checks recorded separately |
| Hooks | Exactly-once calls, literal arguments, timeout/failure behaviour, and suppression during preview |
| Terminal wizard | Page navigation, updated preview, line fallback, cancellation, resize/narrow-terminal handling and no install before confirmation |
| New attachment | Temporary-file install/upgrade/uninstall/drift tests, followed by an isolated real host/session test before an end-to-end claim |

Keep normal verification small. Broaden the matrix when adding a declared
compatibility boundary or resolving a concrete regression. A missing optional
interpreter can skip a local test, but release evidence must name that skip.
Newer versions are candidates for the same checks; they are not automatically
certified by an open-ended version comparison.

## 6. Reproducible PNG gallery

The maintained dashboard matrix is two presets × four output routes × four
themes × two character sets × two colour modes × four terminal sizes: **512
logical captures**. Three static public output formats add **12 captures** at
the same four sizes. Do not invent colour/theme behavior for static notices.

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
