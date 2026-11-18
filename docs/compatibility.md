# Compatibility and login surfaces

Reference date: **2026-11-17**. Separate the machine that runs the configurator,
the interpreter that runs a generated file, and the mechanism that displays it.
A language target is not evidence that every operating system, minor release or
login route has been tested. The v0.4 records are
[Unix presentation evidence](../build/verification-unix-v04.json) and
[PowerShell presentation evidence](../build/verification-powershell-v04.json).
Read their source hashes, exact engines, test modes and limitations. The older
`verification-*-current.json`, `*-legacy.json` and `verification-v03*.json` files
retain v0.3 provenance; they do not verify changed v0.4 renderers. A configured
CI job is not a successful run: consult the job for the exact commit being used.

## One recipe, adaptive outputs

The configurator requires **Python 3.8+**. Generation, recipe recovery and
inspection work across platforms. Python 3.11+ supplies `tomllib`; older supported
Python versions use the bundled, licensed Tomli source, embedded as ordinary
Python. No package download is required by the single-file configurator. Generate
on a capable machine and copy the result to an older destination; Python, TOML
and the repository are not needed at login.
[Python `tomllib` documentation][python] · [Tomli source and compatibility][tomli]

Windows file export uses create-only writes and a hash manifest by default.
`--create-only` selects that route on other hosts too. It refuses existing
destinations and does not create installation state. Export to standard output
is also available. The journalled installation and replacement engine remains
**Linux-only**; Windows and macOS generation do not imply managed profile
installation, upgrade or rollback on those systems. See [installation and
export](install.md) for the two file-writing contracts.

| Output | Selection and compatibility design | Boundary |
|---|---|---|
| Bash | One file selects enhanced Linux collection on Bash 4.3+, or portable Unix collection on older Bash and non-Linux systems. Bash 1, 2, 3, 4 and 5 are distinct major-family targets. | Bash 1 needs an external `printf`. Optional helper availability and OS interfaces determine metrics. Exact historical versions tested are recorded separately. |
| Zsh | A small entry point delegates to `/bin/bash` when present, otherwise `/bin/sh`; the same file then selects the Unix renderer. | This is shared collection, not a second native-Zsh collector implementation. It needs a compatible sh/Bash destination, and does not assume every historical Zsh startup file is identical. |
| Fish | A single file launches its embedded portable Unix payload through `/bin/sh`, forwarding arguments as data. | Requires Fish and `/bin/sh`; collectors remain shared. Large embedded payloads are explicitly bounded. Native startup semantics are tested separately from rendering. |
| Portable sh | All nine section IDs, themes, ASCII/Unicode framing, dynamic row allocation and local Linux/Darwin/BSD/generic-Unix collection paths. | POSIX-like syntax does not imply every historical Bourne dialect, utility option or kernel interface exists. Unavailable data remains unavailable. |
| PowerShell | Native file with PowerShell 1-era grammar, .NET 2-era fallback APIs, literal configuration, and feature checks for newer facilities. Windows PowerShell 1–5 and PowerShell 6–7 are explicit targets. | **PowerShell 1, 3, 4 and 5.0 remain unexecuted targets.** Actual PS2.0 passed 41 cases on Server2022 at the final source commit `4cc3228`. Windows 5.1, PS6 and PS7 evidence are separate. No automatic Windows profile installation. |
| CMD launcher | One `.cmd` file contains the same native PowerShell core as visible text and launches an installed `powershell.exe` or `pwsh.exe`. | Requires a PowerShell engine with `ScriptBlock.Create`; it is not an independent CMD metrics implementation. Treat the wrapper as PS2+ pending older-engine proof. Native filename and argument tests run on Windows. |
| `issue` | Static public text encoded for an agetty-compatible issue consumer. | Not a universal getty escape dialect. |
| `ssh-banner` | Static public text for an explicitly configured OpenSSH `Banner` file. | Generating/writing the file does not reconfigure or reload the server. |
| `text` | Static plain UTF-8 export. | Consumer-specific escaping, legacy code pages and newline conversion are not inferred. |
| `batch-text` | Static ASCII `.cmd` notice using CMD escaping; does not need PowerShell. | No live collectors, hooks, themes or automatic code-page conversion. This is a `cmd.exe` target, not a verified DOS `COMMAND.COM` or OS/2 adapter. |

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

## Executed versions and evidence boundaries

| Family | Executed versions and environment | Evidence scope |
|---|---|---|
| Bash 1–5 | 1.14.7, 2.05b, 3.2.0, 4.3.0 and 5.2.37 on current Linux | Historical source builds and current engine. The v0.4 Unix record covers the changed designs; v0.3 records separately cover startup PTYs and earlier hooks. |
| Zsh 2–5 | 2.3.1, 3.0.8, 4.2.7 and 5.9 on current Linux | Actual entry-point execution and shared collection. Historical startup PTYs are separate from current design checks. |
| Fish | 2.4.0, 3.6.0 and 4.0.2 on current Linux | Actual delegation and literal data tests. The relocated Fish2.4 executable uses local ncurses/tinfo libraries; relocated Fish4 uses `--no-config` because its compiled data-directory path is absent. These test conditions are recorded. |
| Other Unix interpreters | Host dash, BusyBox 1.37.0 ash, mksh R59 and ksh93u+m 1.0.10 on current Linux | Portable generated output under these exact engines. This does not certify every BusyBox build or historical Unix OS. |
| Windows PowerShell 5.1 | Native Windows job passed the design, adapter and export suites at `4cc3228` | The exact engine/OS is in the final native job log. The earlier v0.3 record is retained separately. A 5.1 result does not verify 5.0. |
| PowerShell 6 | 6.2.7 on Linux x86_64 | Native rendering and hooks. This portable runtime requires invariant globalization on this host; the XML/SHA evidence harness additionally needs its historical OpenSSL library, recorded explicitly. |
| PowerShell 7 LTS | 7.6.10 on Linux; the native PowerShell 7 jobs on Windows and macOS passed at `4cc3228` | Native design, geometry, literal data, hooks and missing-data contracts. Consult each native job for its exact patch version and OS. |
| Additional PS7 engine | 7.7.0 on Linux x86_64 | A separately executed engine, not an LTS designation. |
| macOS | Native PowerShell design and cross-platform generation/export suites passed at `4cc3228` | Windows-only adapter execution cases are skipped on macOS. The initial executable-lookup failure was fixed and the native job rerun successfully. Older Bash3.2.57/Zsh5.9 host evidence remains separately recorded. |
| PowerShell 2 | Actual 2.0, CLR2.0.50727.9188, x64 Windows NT10.0.20348.0 / Server2022 at `4cc3228` | **41/41 exact-engine harness cases passed**, including a live local case. The already-available engine needed no optional-component installation. All five artifact hashes match final generation with native Windows CRLF line endings. |
| PowerShell 1, 3, 4 and 5.0; other historical OS images; other Unix hosts | Not execution-verified | Compatibility targets or collector fixtures only. A Windows PowerShell 5.1 pass does not certify 5.0. No blanket all-versions/all-OS claim. |

The v0.3 Unix matrix contains **608 successful cases**, including 8/15-row compact
displays and the requested 25/50-row layouts, with hook, colour and startup
checks recorded separately. It remains historical evidence, not a v0.4 test count.
Some old interpreters needed compiler/platform source fixes to build on modern
Linux; the exact diffs and hashes are retained. These are not pristine binaries
running on their original operating systems.
The [preceding native CI run](https://github.com/Julesc013/motd/actions/runs/43865806375)
records the older Windows/macOS checks; its Linux gallery step intentionally
awaited the subsequent gallery commit. Consult the final revision's CI and v0.4
records for current counts and source hashes. Local isolated-template checks are
labelled separately from integrated generator checks. Neither a YAML workflow nor
a green job with an explicitly skipped PS2 step proves that PS2 executed.

The [first v0.4 native run][native-v04-initial] executed the actual PS2 engine and
the Windows PowerShell 5.1 and PowerShell 7 suites at commit
[`16996e8`](https://github.com/Julesc013/motd/commit/16996e839694a1588d454eba57e4e7def37b0f79).
Its [PS2 evidence artifact][ps2-v04-artifact] includes the unmodified probe and XML:
the XML asserts major2, lists all 41 passing cases and hashes each tested output.
The [final native run][native-v04-final] repeats those checks after the header,
ordering and omission fixes at commit
[`4cc3228`](https://github.com/Julesc013/motd/commit/4cc32280509d02e1d12475060e30f830265f62d0).
All four jobs passed: Windows PowerShell5.1, PowerShell7 on Windows, PowerShell7
on macOS, and actual PowerShell2. Retained [final PS2 XML](../build/verification-powershell2-v04.xml)
and [probe JSON](../build/verification-powershell2-v04-probe.json) preserve the
observations. Each XML artifact hash was regenerated and matched using Windows'
native CRLF output convention. The separate [final workflow artifact][ps2-v04-final-artifact]
preserves the downloaded originals.

The v0.4 Unix record contains **1,000 successful demonstration cases**: 800 cases
across 16 engines, five designs, five sizes and two character sets, plus 200
explicit no-Bash Zsh delegation cases. The five sizes include 40×8 and the four
requested gallery sizes. It separately records **80 live literal-hook checks**
and **42 Fish startup scenarios**. This interpreter matrix captures explicit
geometry through pipes; the gallery supplies separate PTY capture evidence.
The integrated Linux PowerShell record contains **39 passing unit tests
and 41 passing exact-engine harness cases per engine** on 6.2.7, 7.6.10 and 7.7.0.
These counts describe those inputs and hosts, not every possible recipe or OS.

The PS6.2.7 XML harness initially stopped with `No usable version of libssl was
found` on Debian 13. The verification environment supplies an official Debian
libssl1.1 package, checked against its published SHA256, through a process-scoped library path; it does not
install that package into the host. The record includes the package SHA256 and
the required invariant-globalization setting. These are old runtime dependencies,
not generated-MOTD installation steps. [.NET OpenSSL compatibility][dotnet-openssl]
· [Debian libssl1.1 package and hash][libssl11]

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

Runtime overrides accept **40–240 columns and 8–200 rows**. At the requested
**40/80 columns and 25/50 rows**, sections get an explicit budget and retain space
for the next shell prompt. Plain mode and a present `NO_COLOR` disable colours. Portable
historical shells normalize content to printable ASCII and can use known
one-cell Unicode borders; they do not claim a full Unicode-width engine. Font,
code-page and terminal-emulator support remain separate from script syntax.
See the [actual terminal PNG gallery](../examples/gallery/README.md).

The five designs are structural presentations of the same collected sections:
`classic`, framed `cards`, aligned unboxed `ledger`, attention-first `briefing`,
and paired-card `dashboard`. Dashboard preserves the configured section order;
cards sit side by side at wider widths and stack on narrow terminals. `density`,
`padding` and `section_gap` alter spacing;
`detail = "brief" | "normal" | "full"` and `section_detail` alter visible row
allocation. `priority` controls which complete sections survive when space is
short, and `color_emphasis` controls tone intensity. Brief mode promotes an
observation into a briefing headline instead of showing an empty section label.
These are presentation controls, not additional collectors or permission to
relabel unavailable observations. Unix templates embed the shared presentation
source from `runtime/designs.sh`; PowerShell uses the corresponding native core.

Synthetic output keeps a visible DEMO label; the new presentation paths lead
with it so a long title cannot hide it. Their context rows retain host and uptime
within the available geometry. Native PowerShell also retains this context when
System is disabled and places the classic title in its top frame border without
adding a header row. Legacy Unix classic defaults preserve their older layout:
Bash places DEMO at the right of the top border and uptime in System; portable
sh's default subtitle is the site/backend. Disabling System or using an emergency
short layout can therefore remove Unix classic host/uptime context. Long field values may
be shortened to the available width; uptime is explicitly unavailable when no
supported source succeeds. Hidden section names wrap into fully budgeted footer
rows. At 40×8 with many enabled sections, header/context plus the complete hidden
list can consume the viewport, leaving no room for a complete card.

The built-in before/after action `argv = ["motd:print", "literal line"]` prints
data without launching a shell or evaluating expressions. External calls retain
their timeout/failure policy. Both action kinds are suppressed in generated demo
and preview paths; sample previews show declared text only.

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
policy bypass, feature enablement or implicit dependency installation is added
to generated scripts.
The generated source is ASCII even when a recipe contains Unicode: non-ASCII
strings use data-only UTF-8 decoding, avoiding assumptions about an old engine's
file encoding. This does not guarantee that an old terminal font can display
those characters.

### Collecting real legacy evidence

`tools/test_legacy_powershell.ps1` is a standalone evidence harness for a trusted
generated file or directory of generated files. Invoke it with the actual target
engine and `-ExpectedMajor 1..7`. It refuses a different major **before running
the supplied scripts**. Its XML records the exact engine, CLR, OS, bitness,
automation assembly, `ScriptBlock.Create` availability, artifact SHA256 values,
geometry cases and result. `-IncludeLive` adds a local collector smoke case with
hooks suppressed. Python is not required on that destination.

The separate compatibility workflow attempts PS2 only on Windows Server 2022.
It first probes the real engine, then may enable the existing Windows optional
components in that disposable CI VM, and probes again. A missing component or
failed startup produces an explicit blocked record. This does not enable any
feature on the user's destination. Microsoft lists the PS2 component for Server
2022; it removed PS2 from Windows 11 24H2 and Server 2025 during 2025.
[Server 2022 components][server2022] · [Windows removed features][removed-features]
Both the initial and final actual runs found PS2 already available and passed the
harness without installing any component. [Final run and evidence][ps2-v04-final-artifact]

The exact-version harness is also suitable for separately owned older Windows
hosts. This project has not acquired or executed PS1, PS3, PS4 or PS5.0 hosts, and
does not treat source compatibility or installing a reference assembly as such
evidence. The official PS2 example of `ScriptBlock.Create` establishes a PS2
baseline for the CMD wrapper; it is not PS1 execution evidence.
[Microsoft PS2 ScriptBlock example][scriptblock-ps2]

## Shell startup files

| Session interpreter | Appropriate attachment | Important boundary |
|---|---|---|
| Bash | `.bashrc` and the active login file: `.bash_profile`, `.bash_login`, or `.profile` | Login and non-login startup paths differ. A remote noninteractive Bash can read `.bashrc`, so the hook checks actual interactive state and terminal output. |
| Zsh | `.zprofile` and `.zshrc` under `ZDOTDIR`, or the home directory when it is unset | `.zshenv` runs too broadly for a dashboard. System file locations can differ by build; do not assume `/etc/profile.d` is read by Zsh. |
| Portable sh | The selected login profile, normally `.profile`, or an explicit shell-specific startup file | There is no universal portable non-login rc-file location. `ENV` and startup semantics depend on the chosen shell. |
| Fish | The selected `config.fish` under an absolute `XDG_CONFIG_HOME`, or the normal user configuration directory | Managed attachment remains Linux-only and checks interactive terminal state. Fish syntax and startup rules are distinct from sh. |
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
| Windows `cmd.exe` | PowerShell-backed `.cmd` launcher, or ASCII `batch-text` when only a static notice is needed | That every older Windows build has PowerShell, the same font/code page, or tested login integration |
| DOS, OS/2 and Windows 9x | Static text remains the interchange format pending native-host adapter tests | That CMD escaping proves `COMMAND.COM` compatibility, or that those systems can run PowerShell |

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
requirements are present. The wizard and output generation remain on another
machine if the destination cannot run Python 3.8+.

[python]: https://docs.python.org/3.11/library/tomllib.html
[tomli]: https://github.com/hukkin/tomli
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
[server2022]: https://learn.microsoft.com/en-us/windows-server/get-started/editions-comparison?pivots=windows-server-2022
[removed-features]: https://learn.microsoft.com/en-us/windows/whats-new/removed-features
[scriptblock-ps2]: https://devblogs.microsoft.com/scripting/use-powershell-to-combine-multiple-commands-for-ease-of-use/
[dotnet-openssl]: https://learn.microsoft.com/en-us/dotnet/core/compatibility/3.0#net-core-30-prefers-openssl-11x-to-openssl-10x
[libssl11]: https://packages.debian.org/bullseye/amd64/libssl1.1/download
[native-v04-initial]: https://github.com/Julesc013/motd/actions/runs/43995922674
[ps2-v04-artifact]: https://github.com/Julesc013/motd/actions/runs/43995922674/artifacts/14290006975
[native-v04-final]: https://github.com/Julesc013/motd/actions/runs/43997494337
[ps2-v04-final-artifact]: https://github.com/Julesc013/motd/actions/runs/43997494337/artifacts/14290472775

[ps-lifecycle]: https://learn.microsoft.com/powershell/scripting/install/powershell-support-lifecycle?view=powershell-7.6
[bash-releases]: https://ftp.gnu.org/gnu/bash/
[zsh-releases]: https://www.zsh.org/pub/old/
