# Shell outputs, login surfaces and visual configuration

Status: **implementation contract and bounded extension plan**, 2026-11-16.
This extends the original v0.1 scope. Requirements describe acceptance behaviour;
they do not constitute a claim that every listed host has passed testing.
The [compatibility guide](../docs/compatibility.md) records primary-source reasons
for the version and attachment boundaries.

## 1. Preserve the small design

Keep one downloadable Python configurator, TOML recipes, a small set of embedded
canonical output templates, and one transaction engine. Add an output backend
when its interpreter requires different syntax. Reuse the Bash renderer through
a Zsh launcher instead of maintaining a second copy of all its collectors.

Separate these choices in the recipe and UI:

| Choice | Meaning |
|---|---|
| Action | Create, install, inspect, audit, repair, reconfigure, upgrade, recover, rollback or uninstall |
| Target | Interactive shell output, agetty issue text, OpenSSH banner text, or generic static text |
| Shell | Bash, Zsh launcher, native PowerShell, or reduced native sh output |
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
3. Zsh output declares its Bash dependency. It must not describe itself as a
   native Zsh collector implementation.
4. Native sh output avoids Bash arrays, namerefs and Bash-only substitutions.
   Reduced collection is explicit; unavailable data is not presented as zero,
   healthy, or measured.
5. PowerShell output targets Windows PowerShell 5.1 syntax and PowerShell 7.
   Host capability checks determine available collectors. A PS7/Linux test does
   not establish PS5.1/Windows compatibility.
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
| Bash full renderer | Minimum-version syntax/runtime smoke plus a current Bash; no configuration injection or metric semantic changes |
| Zsh launcher | Actual Zsh invocation, correct argument forwarding, duplicate/interactive guards, and the shared Bash demonstration |
| Portable sh | At least dash plus a BusyBox ash build before claiming both; restricted environment and missing-utility behaviour |
| PowerShell | Actual Windows PowerShell 5.1 and PS7 parsing/demo/quoting checks; OS-specific collector checks recorded separately |
| Hooks | Exactly-once calls, literal arguments, timeout/failure behaviour, and suppression during preview |
| Terminal wizard | Page navigation, updated preview, line fallback, cancellation, resize/narrow-terminal handling and no install before confirmation |
| New attachment | Temporary-file install/upgrade/uninstall/drift tests, followed by an isolated real host/session test before an end-to-end claim |

Keep normal verification small. Broaden the matrix when adding a declared
compatibility boundary or resolving a concrete regression. A missing optional
interpreter can skip a local test, but release evidence must name that skip.
Newer versions are candidates for the same checks; they are not automatically
certified by an open-ended version comparison.
