# motd

A small configurator for messages of the day. Start from a preset, preview the sections and presentation, then generate a standalone shell script or a static login notice.

The configurator runs on **Linux with Python 3.11 or later and the standard library**. Generated displays do not need Python, TOML, this repository, or the configurator at login. Choose **Bash, Zsh, portable sh, or native PowerShell** output. Their dependencies and collector coverage differ; see the [compatibility guide](docs/compatibility.md).

Version 0.2 adds a page-by-page terminal wizard with previews, additional shell outputs, and a bounded compatibility specification. Workshop and home-lab are configurations over shared templates. Automatic installation remains Linux-specific; PowerShell output can be built and copied to its destination, while PowerShell profile installation is still manual.

## Start here

Download `motd.py` and run:

```sh
python3 motd.py
```

Download-and-run convenience command (requires Python 3.11+):

```sh
curl -fL -o motd.py https://raw.githubusercontent.com/Julesc013/motd/main/motd.py && python3 motd.py
```

The download is a readable local file. You can inspect it before running the
second command. Pin `main` to a reviewed commit SHA when deploying an exact
version. The wizard requires a terminal; piping source into Python would consume
the same standard input it needs for questions.

The opening menu asks what you want to do: **create, install, reconfigure, inspect/audit, repair, recover, uninstall, or rollback**. `python3 motd.py wizard` opens the same workflow.

On a suitable terminal, the wizard uses successive screens with numbered choices. Destination, appearance, sections, content and hooks are grouped into pages. Appearance choices show a synthetic preview; you can go back, request a full preview, review the installation plan, save/build, or cancel. Choosing options does not install anything.

Select the presentation explicitly when needed:

```sh
python3 motd.py wizard --ui screen
python3 motd.py wizard --ui line
```

The default `--ui auto` selects the screen interface for a compatible terminal at least 60 columns by 20 rows, with a line-mode fallback. No curses package or GUI toolkit is required. For command-line options:

```sh
python3 motd.py --help
```

This is a page rendered by the actual wizard with synthetic fixture data:

![Wizard theme selection with a preview](examples/wizard-theme.svg)

For a quick command-line workflow:

```sh
python3 motd.py preview --preset workshop
python3 motd.py build --preset workshop --output ./workshop.bash --save-config ./workshop.toml
python3 motd.py plan --config ./workshop.toml --target shell --scope user --audience ssh --name workshop
python3 motd.py install --config ./workshop.toml --target shell --scope user --audience ssh --name workshop
```

Preview uses demonstration data by default. Add `--live` to collect local information; both modes suppress before/after commands for generated recipes. A recognized imported recipe is regenerated for preview. Explicit `--live --trust-artifact` execution of an opaque script can have that script's normal side effects. Installation presents the plan and asks before applying it. `--yes` applies a noninteractive installation, so review `plan` first when automating.

Presets are `workshop`, `home-lab`, and `public-console`. You can instead use `--config FILE` or recover a generated script's configuration with `--artifact FILE`. Keep the configuration and generated output; installation transactions also archive them for inspection and recovery. Choose an existing parent directory for generated or installed files.

## Choose an interpreter

```sh
python3 motd.py build --preset workshop --shell bash --output ./workshop.bash
python3 motd.py build --preset workshop --shell zsh --output ./workshop.zsh
python3 motd.py build --preset workshop --shell sh --output ./workshop.sh
python3 motd.py build --preset workshop --shell powershell --output ./workshop.ps1
```

| Output | Behaviour |
|---|---|
| Bash | Full Linux dashboard; Bash 4.3+, Linux/procfs and GNU `timeout`, plus optional collector commands. |
| Zsh | Standalone Zsh launcher for that same Bash renderer. Bash is still required. |
| sh | Reduced native POSIX-shell display, with basic local `/proc` observations when available. Richer unsupported collectors are labelled. |
| PowerShell | Native `.ps1` renderer targeting Windows PowerShell 5.1 syntax and PowerShell 7. OS-specific collectors differ; this is not full Bash telemetry parity. |

Generate on a modern Linux machine and copy the file to a destination that lacks Python 3.11. A targeted language version is distinct from a verified OS/version combination; the [compatibility matrix](docs/compatibility.md) and test records state that distinction.

## Copyable examples

The files in [examples](examples/README.md) are complete portable outputs. Their
recipes are in [presets](presets). Generate once, then copy the output by USB,
SSH or your existing deployment tool. Only attaching it to login needs installation.

The following gallery is rendered from synthetic fixture data by the actual engine:

![Workshop synthetic preview](examples/workshop.svg)

![Home-lab synthetic preview](examples/home-lab.svg)

Ordinary configuration is data. Optional commands are explicit argument arrays; shell expressions require an explicitly chosen shell invocation. Inspecting an existing script does not execute it.

## Choose a destination

| Target and scope | Output and audience |
|---|---|
| `--target shell --scope user` | A Bash, Zsh or sh display for the selected user's eligible interactive terminal sessions on Linux. |
| `--target shell --scope system` | A host-managed Linux shell hook; the display runs with the session user's permissions. Zsh and nonstandard startup routes need an explicit appropriate file. |
| `issue` | A static public notice for the console login screen used by agetty. |
| `ssh-banner` | A static public notice for OpenSSH before authentication. |
| `text` | Generic static text for a deliberately selected consumer or destination. |

For shell output, `--audience all|ssh|local` selects eligible sessions. `local` means SSH markers are absent; it does not prove a physical console. The Bash system default uses `/etc/profile.d` for login shells; other startup routes need a host-appropriate `--shell-file`. Static targets do not run hooks or refresh on each connection. Generated issue notices escape agetty backslashes; generic text has no consumer-specific escaping. Imported static artifacts retain their existing bytes. See [installation and target contracts](docs/install.md).

## Existing scripts and later changes

A shell output generated by this project carries metadata from which the configurator can recover its configuration:

```sh
python3 motd.py config --artifact ./workshop.bash --output ./recovered.toml
```

Static outputs contain only public text; retain their TOML recipe or archive to reconfigure them. Installing an existing executable file's exact bytes requires `--trust-artifact`, even when it carries metadata. An arbitrary script has no inferred editable model. The import records a SHA-256 fingerprint; it does not establish authorship. Rewritten TOML preserves supported settings, not original comments or formatting.

Reconfigure managed outputs through the configurator. `repair --name NAME` uses the current installation manifest across upgrades and restores missing owned files while preserving modified ones. Rollback reverses a completed transaction only when later ownership and file changes allow it; recovery reverses an interrupted apply. Review each plan and keep unrelated files outside the installation's ownership. See the [recovery limits](docs/install.md#recovery-boundaries) for what the archive preserves.

## Project layout and decisions

`runtime/` holds canonical Bash, portable sh and PowerShell templates. The downloadable `motd.py` embeds them so users need only one configurator file. Zsh reuses the Bash template. TOML presets select content and appearance; generated examples are rebuilt from those sources.

`reference/` preserves the original workshop and home-lab scripts, workshop guide, verification record, and provenance. Those imports provide history and comparison material; changes belong in the canonical runtime and configurator.

- [Design and language choice](docs/design.md)
- [Configuration and before/after commands](docs/configuration.md)
- [Installation, imports, and recovery](docs/install.md)
- [Compatibility and login surfaces](docs/compatibility.md)
- [Current shell, surface and wizard specification](specs/compatibility.md)
- [Historical v0.1 acceptance contract](specs/v0.1.md)

BusyBox/BSD getty adapters, PAM integration, Windows installation, RDP desktop-start notices, and DOS/OS/2 wrappers are specified separately as future work. Existing SSH/Telnet terminal sessions can use an eligible shell hook; an RDP desktop does not provide a generic text-banner destination.

## Verification

Tests cover configuration recovery, literal quoting, interpreter demonstrations,
hooks, adaptive fixtures, wizard flows, noninteractive guards, installation/removal,
undo/redo and injected interruption recovery. A skipped optional interpreter test
does not establish support for that interpreter.

The [verification records](build/) and the current GitHub Actions run identify
tested sources and limits. Real SSH/PAM/agetty installation, root-only ownership
restoration and older OS combinations need their own host evidence. Run:

```sh
python3 tools/embed_runtime.py --check
python3 -m unittest discover -s tests -v
```

## License

A license has not yet been selected. Resolve the project license and the provenance of included material before assigning redistribution terms or publishing third-party redistribution instructions.
