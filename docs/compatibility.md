# Compatibility and login surfaces

Reference date: **2026-11-16**. This page separates the machine that runs the
configurator, the interpreter that runs an output, and the mechanism that displays
it. A generated file is not evidence that every operating system or login route
has been tested. Consult the current CI run and `build/` records for observed
results; a skipped interpreter test is not a pass.

## Choose the output, then its attachment

The configurator uses Linux and Python 3.11 or later. Python's standard-library
TOML reader first appeared in 3.11. Generate on a suitable machine and copy the
output to an older destination; the destination does not need Python or the
repository to display it. The current transaction engine is Linux-specific.
Generating PowerShell does not make that installer a Windows installer.
See [Python's `tomllib` documentation][python].

| Output | Required or intended baseline | Coverage and boundary |
|---|---|---|
| Bash dashboard | Linux/procfs, Bash 4.3+, GNU `timeout` | Full workshop renderer. Optional collectors depend on their utilities and permissions. Local checks use Bash5.2.37, plus a Bash4.3.0 syntax/demo/direct-worker smoke on current Linux. This does not certify every intervening release or an old OS. |
| Zsh output | Zsh launcher, plus the same Linux/Bash dependencies | A standalone `.zsh` entry point delegates to the shared Bash renderer. This is intentional reuse; it is not a native Zsh port of the collectors. Zsh 5.9 is exercised locally. |
| Portable `sh` output | POSIX-compatible shell; dash is exercised locally | A reduced display for older/minimal environments. It reads a few fixed Linux `/proc` files, using shell builtins, and shows unavailable states elsewhere. Base rendering needs no external collector. This does not cover every historical Bourne-shell dialect. |
| PowerShell output | Windows PowerShell 5.1 language baseline; PowerShell 7+ | Native `.ps1` output with no Bash dependency. PS7.7/Linux demonstration execution is exercised locally; Windows5.1 requires its separate test. Collector availability varies by OS. A language baseline does not certify an old Windows installation. |
| `issue` | An agetty-compatible issue consumer | Static public text with agetty literal-backslash escaping. Not a generic format for every getty implementation. |
| `ssh-banner` | An OpenSSH server configured to read the file | Static public text sent before authentication. Writing the file does not configure or reload the server. |
| Generic `text` | A consumer of plain UTF-8 text | Static export without agetty escape conversion. Select the destination and verify its interpretation explicitly. Legacy code pages and CRLF conversion are not inferred. |

Bash 4.3 is a meaningful boundary: the renderer uses `local -n` namerefs, introduced
in that release. Bash 3.2 or 4.2 must use the portable output or a separately
installed compatible Bash; the generator does not silently replace a shell.
See the [GNU Bash 4.3 release announcement][bash43].
The [minimum-version smoke record](../build/verification-bash43.json) pins the
final canonical template, matching generated example and interpreter source used
for the Bash 4.3.0 syntax, synthetic-renderer and direct-worker checks.
An actual Bash 3.2.0 run also verified rejection of the full renderer before hooks
execute, and successful native sh demonstration output; see the
[older-interpreter boundary record](../build/verification-bash32.json). Both
historical interpreters were built on current Linux, not a historical OS image.

The native outputs have deliberately smaller coverage:

| Capability | Portable sh | PowerShell |
|---|---|---|
| Identity/resources | Host/kernel, uptime/load and memory from bounded fixed-file `/proc` reads when present | Identity/CPU count; Linux `/proc` memory or Windows CIM memory; system volume |
| Services/processes | Explicitly not collected | Windows services; process lifetime CPU seconds and working set where available |
| Detailed I/O, sessions, connections | Explicitly not collected | Unsupported detail is labelled; no full process-I/O-rate or session-inventory parity |
| Hooks | External commands require a GNU-compatible `timeout`; no timeout utility means failure/skip before execution, following the selected policy | Explicit executables/interpreters; timeout stops the direct process on PS5.1 and attempts its descendant tree on current PS7/.NET |

PowerShell does not claim the Bash worker's whole-render deadline. A Windows CIM
operation's timeout does not include all module initialization. A hook timeout
is not a sandbox or a universal guarantee against descendant processes. Native
sh/PowerShell layout also does not claim a complete Unicode terminal-cell-width
implementation. These are versioned capability boundaries, not hidden equivalents
of the full Bash view.

Portable shell syntax does not imply portable metrics. `/proc`, service managers,
`ps` options and available utilities differ across Linux, BSD, macOS and embedded
systems. BusyBox also permits individual applets and features to be excluded at
build time. A BusyBox version number alone cannot establish all dependencies.
See the [BusyBox manual][busybox].

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
