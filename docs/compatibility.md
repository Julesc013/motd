# Compatibility and login surfaces

Reference date: **2026-11-17**. Separate the machine that runs the configurator,
the interpreter that runs a generated file, and the mechanism that displays it.
A language target is not evidence that every operating system, minor release or
login route has been tested. Exact local commands, source hashes and skips live in
[current Unix evidence](../build/verification-unix-current.json),
[current PowerShell evidence](../build/verification-powershell-current.json),
[final local verification](../build/verification-v03-final.json) and revision-specific CI.
The older `*-legacy.json` and `verification-v03.json` files retain the preceding
checks and historical build provenance; they are not substituted for current results.

## One recipe, adaptive outputs

The configurator uses **Linux and Python 3.11+**. Generate there and copy an output
to an older destination; Python and the repository are not needed at login. The
transaction engine is still Linux-specific. Generating a Windows-compatible
PowerShell script does not make that engine a Windows installer.
[Python `tomllib` documentation][python]

| Output | Selection and compatibility design | Boundary |
|---|---|---|
| Bash | One file selects enhanced Linux collection on Bash 4.3+, or portable Unix collection on older Bash and non-Linux systems. Bash 1, 2, 3, 4 and 5 are distinct major-family targets. | Bash 1 needs an external `printf`. Optional helper availability and OS interfaces determine metrics. Exact historical versions tested are recorded separately. |
| Zsh | A small entry point delegates to `/bin/bash` when present, otherwise `/bin/sh`; the same file then selects the Unix renderer. | This is shared collection, not a second native-Zsh collector implementation. It needs a compatible sh/Bash destination, and does not assume every historical Zsh startup file is identical. |
| Portable sh | All nine section IDs, themes, ASCII/Unicode framing, dynamic row allocation and local Linux/Darwin/BSD/generic-Unix collection paths. | POSIX-like syntax does not imply every historical Bourne dialect, utility option or kernel interface exists. Unavailable data remains unavailable. |
| PowerShell | Native file with PowerShell 1-era grammar, .NET 2-era fallback APIs, literal configuration, and feature checks for newer facilities. Windows PowerShell 1–5 and PowerShell 6–7 are explicit targets. | **PowerShell 1–4 have not been execution-verified.** Windows 5.1, PS6 and PS7 evidence are separate. No automatic Windows profile installation. |
| `issue` | Static public text encoded for an agetty-compatible issue consumer. | Not a universal getty escape dialect. |
| `ssh-banner` | Static public text for an explicitly configured OpenSSH `Banner` file. | Generating/writing the file does not reconfigure or reload the server. |
| `text` | Static plain UTF-8 export. | Consumer-specific escaping, legacy code pages and newline conversion are not inferred. |

Bash 4.3 remains the enhanced renderer's boundary because it introduced the
namerefs that renderer uses. The generated file now embeds a portable branch
**before** modern syntax: an older engine executes that branch and exits without
parsing the later Bash body. It does not install or upgrade a shell.
[GNU Bash 4.3 announcement][bash43]

Do not call Bash 1–5 or Zsh major families "LTS releases" in the test matrix.
PowerShell has its own explicit support lifecycle: **7.6 is the current LTS line**
as of the reference date. Legacy-language compatibility here does not restore a
vendor's retired OS or engine support. The exact 7.x patch tested belongs in the
record, rather than the open-ended label "7 or newer".
[Microsoft PowerShell lifecycle][ps-lifecycle] · [GNU Bash releases][bash-releases]
· [Zsh release archive][zsh-releases]

## Executed versions for this revision

| Family | Executed versions and environment | Evidence scope |
|---|---|---|
| Bash 1–5 | 1.14.7, 2.05b, 3.2.0, 4.3.0 and 5.2.37 on current Linux | Historical source builds and current engine; generated display, geometry and hooks. Selected Bash 1/2 startup guards also use real interactive PTYs. |
| Zsh 2–5 | 2.3.1, 3.0.8, 4.2.7 and 5.9 on current Linux | Actual entry-point execution, shared Bash path and a fixture that models missing Bash. Zsh 2 startup guards are exercised in a real interactive PTY. |
| Portable sh | Host dash, plus the above historical Bash engines | Generated portable output, four geometries, missing helpers and collector fixtures. This is not a claim about every BusyBox build. |
| Windows PowerShell 5.1 | 5.1.26100.33648 on Windows Server 2025 Datacenter, build 10.0.26100 in the preceding native run | The final revision has a separate 25-test native CI gate; consult that revision's job result. |
| PowerShell 6 | 6.2.7 on Linux x86_64 | All 25 native tests; this portable runtime requires invariant globalization on this host. |
| PowerShell 7 LTS | 7.6.10 on Linux; 7.6.9 on Windows Server 2025 | Native execution and geometry, literal configuration, hooks, error/missing-data behavior. |
| Additional PS7 engine | 7.7.0 on Linux x86_64 | A separately executed engine, not an LTS designation. |
| macOS | 26.7.2 arm64 with built-in Bash 3.2.57 and Zsh 5.9 | Four native-host tests: real generated files, local identity/collectors, geometry and delegation. |
| PowerShell 1–4 and 5.0; other historical OS images; other Unix hosts | Not execution-verified | Compatibility targets or collector fixtures only. A Windows PowerShell 5.1 pass does not certify 5.0. No blanket all-versions/all-OS claim. |

The current Unix matrix contains **608 successful cases**, including 8/15-row
compact displays and the requested 25/50-row layouts, with ten live hook checks,
twelve older-Bash colour checks and eighteen historical startup scenarios
recorded separately. Some old interpreters needed compiler/platform source fixes
to build on modern Linux; the exact diffs and hashes are in the Unix record.
They were not pristine binaries running on their original operating systems.
The [preceding native CI run](https://github.com/Julesc013/motd/actions/runs/43865806375)
records the older Windows/macOS checks; its Linux gallery step intentionally
awaited the subsequent gallery commit. Consult the final revision's CI for the
complete release gate. The current Linux PowerShell record contains 25 passing
tests on each of 6.2.7, 7.6.10 and 7.7.0. Counts are test evidence, not a census
of all environments.

## Shared sections, explicit metric semantics

All renderers expose `system`, `resources`, `services`, `processes`, `sessions`,
`connections`, `attention`, `hints`, and `io`. The recipe selects and orders them.
Collectors use the destination's actual facilities; a matching section name does
not make measurements from different APIs interchangeable.

| Observation | Portable Unix | Native PowerShell |
|---|---|---|
| Identity and uptime | Linux procfs; `uname`, `sysctl` and local helpers elsewhere | Environment/.NET and Linux procfs or guarded Windows management APIs |
| Memory and storage | Linux MemAvailable; Darwin/BSD free/total memory where queryable, labelled distinctly; `df -Pk` | Linux procfs, Windows CIM/WMI, system-volume drive data; BSD/macOS total memory can be available while used memory is unavailable |
| Services | systemd, OpenRC and selected BSD rc queries when present; enabled scripts are not described as running | Windows services, guarded systemd queries and basic launchd inventory |
| Processes | Visible `ps` sample for CPU percentage and RSS; capped Linux procfs I/O reads | Lifetime CPU seconds and working-set bytes; Windows/Linux I/O counters where accessible |
| I/O | Cumulative process bytes where available; no portable live device-rate collector | Cumulative process bytes, not a sampled rate; Windows transfer counts have different scope from Linux storage-accounted bytes |
| Sessions/connections | Local `who`, procfs/socket utilities where supported | `who`/`quser` or explicitly limited current-user view; local .NET TCP/UDP APIs |
| Pressure/compression/journal | Linux pressure where available; unsupported facilities state unavailable | Linux memory pressure where available; live compression and event/journal detail unavailable |
| Hooks | Literal argv, timeout and failure policy; missing compatible hook timeout means skip/failure before executing it | Literal argv through process APIs; legacy engines can terminate the direct child, newer .NET can attempt a process-tree kill |

The portable renderer uses bounded helper captures and per-helper timeouts or a
direct-child watchdog where supported. It does not inherit the enhanced Bash
worker's whole-render deadline. PowerShell likewise has no hard total deadline
around WMI/provider initialization or native .NET calls. A hook timeout is not a
sandbox or universal descendant-process containment.

At **40/80 columns and 25/50 rows**, sections get an explicit row budget and retain
space for the next shell prompt. Wider values and additional detail are emitted
by the runtime. Plain mode and a present `NO_COLOR` disable colours. Portable
historical shells normalize content to printable ASCII and can use known
one-cell Unicode borders; they do not claim a full Unicode-width engine. Font,
code-page and terminal-emulator support remain separate from script syntax.
See the [actual terminal PNG gallery](../examples/gallery/README.md).

Saved recipes can select `display.charset = "auto" | "ascii" | "unicode"` and
`display.color = "auto" | "always" | "never"`. These are defaults; explicit
runtime flags can override them, while plain mode, `NO_COLOR` and mono retain
colour suppression. Automatic character selection follows each backend's existing
capability policy; portable old-shell output defaults to ASCII.

The wizard reserves ten control rows and renders into the remaining viewport.
POSIX input tests exercise resizing without pressing Enter, preservation of a
partially typed answer, stale inherited geometry, and terminal-state restoration
after EOF/Ctrl-C. The screen UI accepts 40×18 and larger terminals, with a line
fallback; a resized window below the minimum retains the pending answer.

Portable syntax does not guarantee portable metrics. Linux procfs, BSD sysctl,
service managers, `ps` options and available utilities differ. BusyBox permits
individual applets/features to be excluded at build time, so its version number
alone is not sufficient evidence. [BusyBox manual][busybox]

## PowerShell launch on older engines

A normal interactive invocation works without relying on the newer executable
`-File` launch switch:

```powershell
& 'C:\path\workshop.ps1' -Demo -Plain
```

From an existing Windows command prompt, the legacy-compatible form is:

```text
powershell.exe -NoProfile -Command "& 'C:\path\workshop.ps1' -Demo -Plain"
```

PowerShell 2+ can also use `-File`. Effective execution policy still applies; no
policy bypass, feature enablement or implicit dependency installation is added.
The generated source is ASCII even when a recipe contains Unicode: non-ASCII
strings use data-only UTF-8 decoding, avoiding assumptions about an old engine's
file encoding. This does not guarantee that an old terminal font can display
those characters.

## Shell startup files

| Session interpreter | Appropriate attachment | Important boundary |
|---|---|---|
| Bash | `.bashrc` and the active login file: `.bash_profile`, `.bash_login`, or `.profile` | Login and non-login startup paths differ. A remote noninteractive Bash can read `.bashrc`, so the hook checks actual interactive state and terminal output. |
| Zsh | `.zprofile` and `.zshrc` under `ZDOTDIR`, or the home directory when it is unset | `.zshenv` runs too broadly for a dashboard. System file locations can differ by build; do not assume `/etc/profile.d` is read by Zsh. |
| Portable sh | The selected login profile, normally `.profile`, or an explicit shell-specific startup file | There is no universal portable non-login rc-file location. `ENV` and startup semantics depend on the chosen shell. |
| PowerShell | The intended host's `$PROFILE` or one of its explicit scope properties | Windows PowerShell 5.1 and PowerShell 7 use different profile trees. Host-specific profiles also differ. Query `$PROFILE` in the target host instead of guessing a common path. |

References: [Bash startup files][bash-startup], [Zsh startup files][zsh-startup],
[PowerShell profiles][ps-profiles], and [migration from 5.1 to 7][ps-migration].

PowerShell profile execution depends on the effective Windows execution policy.
The project does not bypass that policy or change it implicitly. PowerShell
remoting sessions do not automatically load normal profiles, and a PowerShell
SSH subsystem is different from an ordinary terminal login. Do not insert human
dashboard text into PSRP, WinRM, SFTP, or other machine-readable streams.
See [execution policies][ps-policy], [remote profile behaviour][ps-profiles], and
[PowerShell SSH remoting][ps-ssh].

## Console and remote routes

| Surface | Supported approach or specified next step | What the project does not infer |
|---|---|---|
| Linux virtual console / serial console with agetty | Generate `issue`; install to an explicitly reviewed file | Which getty instance reads it, whether issue output is disabled, terminal geometry or serial encoding |
| BusyBox `getty` / `telnetd` | Export public text; a dedicated tested adapter may follow | agetty's complete escape dialect or directory search rules. BusyBox documents a selectable issue file; verify the installed applet and its build options. |
| BSD `getty` | Export text and use a future explicit `gettytab` adapter | Linux paths or escaping. FreeBSD documents `if` for an initial file and `%` substitutions, which differ from agetty. |
| OpenSSH before authentication | Generate `ssh-banner`; administrator selects `Banner` | That `/etc/issue` or `/etc/issue.net` is automatically read by OpenSSH |
| SSH after authentication | Guarded interactive shell attachment, with the selected interpreter | Every SSH connection starts a terminal or loads the same profile |
| Existing PAM/login MOTD route | Static text export; future explicit distro adapter | That upstream PAM, distro `update-motd` scripts and shell profiles are interchangeable |
| Existing Telnet login route | Guarded shell output after login; public text before login where supported | That SSH environment variables identify Telnet, or that this project provisions or secures the Telnet service |
| RDP session | Run the output in an interactive terminal inside the session | That RDP provides a generic text-MOTD slot. An automatic desktop-start notification is a separate future adapter. |
| Windows sign-in notice | Export suitable public text; policy integration is separately specified | Permission to change local/domain security policy, or that it is a PowerShell profile |
| DOS, OS/2, Windows 9x, old cmd.exe | Static text is the initial interchange format; native command wrappers are future work | PowerShell support, Unicode/ANSI support, automatic code-page conversion or live-metrics parity |

The agetty issue search rules changed across versions: additional `/run` and
`/usr/lib` locations arrived in 2.35, and their interaction with `/etc/issue`
changed again in 2.41. Review the installed implementation and arguments before
choosing a drop-in location. The current explicit file route avoids depending
on one universal drop-in rule. [agetty manual][agetty]

FreeBSD's `gettytab` and BusyBox's getty/telnetd documentation establish that
alternative consumers exist, not that this release has tested their integration.
[FreeBSD gettytab][gettytab] · [BusyBox manual][busybox]

OpenSSH distinguishes preauthentication `Banner` from post-login `PrintMotd`.
Ubuntu also documents a distribution-specific `pam_motd` update-script route.
Choose one deliberate display route rather than silently disabling the machine's
other notices. [OpenSSH configuration][openssh] · [Ubuntu pam_motd][ubuntu-motd]

RDP presents a graphical user session. Windows' interactive sign-in message is
a separate security-policy setting. These can consume related content but are
separate integration jobs. [Microsoft RDS overview][rdp] · [Windows sign-in
message policy][windows-notice]

The existing `audience = "local"` selection means **no SSH environment marker was
found**. It does not prove a physical console: Telnet, an RDP-launched terminal,
or another local-looking shell may qualify. The project does not invent a
universal transport detector.

## Older and newer systems

Keep compatibility claims in three categories:

- **Verified:** a named interpreter/OS and a recorded command or CI test passed.
- **Targeted:** syntax and capability boundaries are deliberate, but that exact
  host/version still needs validation.
- **Specified:** an integration contract exists; implementation is future work.

There is no promise of support for every historic or future release. A new shell
major version should pass the same parsing, demonstration, quoting, hook,
noninteractive and installation checks before being added to the verified set.
OS support must be recorded separately. Microsoft's WMF history illustrates why:
an older Windows release may accept one PowerShell family but not another.
[WMF availability history][wmf]

For a very old or constrained destination, choose plain static text first, then
portable sh if the interpreter exists. Use the richer renderer only when its
requirements are present. The wizard and output generation remain on the modern
machine if the destination cannot run Python 3.11.

[python]: https://docs.python.org/3.11/library/tomllib.html
[bash43]: https://lists.gnu.org/archive/html/info-gnu/2014-02/msg00010.html
[bash-startup]: https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files
[zsh-startup]: https://zsh.sourceforge.io/Doc/Release/Files.html
[busybox]: https://busybox.net/downloads/BusyBox.html
[ps-profiles]: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_profiles?view=powershell-5.1
[ps-migration]: https://learn.microsoft.com/powershell/scripting/install/migrating-from-windows-powershell-51-to-powershell-7
[ps-policy]: https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
[ps-ssh]: https://learn.microsoft.com/en-us/powershell/scripting/security/remoting/ssh-remoting-in-powershell
[agetty]: https://man7.org/linux/man-pages/man8/agetty.8.html
[gettytab]: https://man.freebsd.org/cgi/man.cgi?query=gettytab&sektion=5
[openssh]: https://man.openbsd.org/sshd_config
[ubuntu-motd]: https://ubuntu.com/server/docs/reference/other-tools/pam-motd/
[rdp]: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-rdsod/5637838a-efff-4d5d-b42a-7645addbbdb9
[windows-notice]: https://learn.microsoft.com/en-us/windows/security/threat-protection/security-policy-settings/interactive-logon-message-text-for-users-attempting-to-log-on
[wmf]: https://learn.microsoft.com/en-us/powershell/scripting/windows-powershell/wmf-overview

[ps-lifecycle]: https://learn.microsoft.com/powershell/scripting/install/powershell-support-lifecycle?view=powershell-7.6
[bash-releases]: https://ftp.gnu.org/gnu/bash/
[zsh-releases]: https://www.zsh.org/pub/old/
