# Installation and recovery

The configurator requires Python 3.8 or later. Generation, recipe recovery and create-only export are available across supported Python hosts; the managed transaction engine and startup-file installation target Linux.
Select Bash, Zsh, native sh or Fish for managed Linux shell installation. Native
PowerShell and CMD output can be generated and copied elsewhere; PowerShell profile
installation is not managed in this version. Output dependencies are listed in
the [compatibility guide](compatibility.md).

Start with `python3 motd.py`. The wizard uses screens and synthetic previews on a
suitable terminal; `wizard --ui line` retains sequential prompts. The CLI remains
available for direct build, preview and management commands.

## Plan before applying

Select the action and destination, then review the plan. `plan` is read-only. `install` presents the plan and asks before applying it; `--yes` provides explicit noninteractive application. System scope requires root. Its files and ancestor directories must be root-owned and not writable by group or others; user-scoped installation should not require system privileges.

```sh
python3 motd.py plan --preset home-lab --target shell --scope user --audience all --name home-lab
python3 motd.py install --preset home-lab --target shell --scope user --audience all --name home-lab
```

Build and preview accept the implemented output backends; managed installation
accepts supported Linux attachments. Inputs can be a preset, TOML recipe or
recognized generated artifact. Overrides include `--target`, `--shell`, `--scope`,
`--audience`, `--name`, `--destination` and `--shell-file`. `--state-dir` selects the
transaction store. Destination parents must already exist; the tool creates its
private state tree, not arbitrary destination directory trees.

An installation owns its recorded files or explicitly marked integration region. It does not acquire ownership of every MOTD, shell startup file, or SSH setting on the host. An unmanaged artifact destination requires `--replace` to take ownership with a backup, except for the `issue` target's explicitly planned replacement. Changed files and conflicting integrations must be made visible before replacement or removal.

## Target contracts

| Target and scope | Integration contract | Boundary |
|---|---|---|
| `shell`, Bash user | Installs a `.bash` output and guarded blocks in `.bashrc` and the active Bash login file. | Interactive terminal sessions only. |
| `shell`, Zsh user | Installs a `.zsh` output and guarded blocks in `.zshrc` and `.zprofile` under `ZDOTDIR` or the home directory. | The output delegates through `/bin/bash`, or `/bin/sh` when Bash is absent. |
| `shell`, sh user | Installs a `.sh` output and a guarded login-profile attachment. | Portable native renderer; other startup routes need an explicit appropriate file. |
| `shell`, Fish user | Installs a `.fish` launcher and a guarded block in `$XDG_CONFIG_HOME/fish/config.fish` or `~/.config/fish/config.fish`. | The parent directory must already exist; the output needs `/bin/sh`. Uses Fish interactive/login checks and a per-process duplicate marker. |
| `shell`, system | Installs `/usr/local/bin/motd-ID`; Bash uses `/etc/profile.d/70-motd-ID.sh` by default. | Zsh and nonstandard routes need an explicit startup file. No assumption that all shells read `/etc/profile.d`. |
| `shell`, PowerShell or CMD | Build/export only. | No automatic PowerShell profile or Windows managed installation. A CMD dashboard needs a compatible installed PowerShell. |
| `issue` | Installs static public text; the system default is `/etc/issue`, with explicit backup/replacement. | agetty reads text, not Bash. Custom agetty options can select another file or disable issue display. |
| `ssh-banner` | Installs static public text; the system default is `/etc/ssh/motd-ID.banner`. | OpenSSH must reference that file through `Banner`. Installing the file is not proof that it is enabled. |
| `text` | Exports or installs generic static text to an explicit destination. | No inferred consumer, encoding conversion, authentication configuration or default system file. |
| `batch-text` | Generates an ASCII `.cmd` notice for Windows NT CMD. | Literal notice only; no collectors, PowerShell requirement or automatic Windows login attachment. |

`ID` is the value of `--name`. Static user-scope installations require an explicit
`--destination`; generic `text` always requires one for installation. Other static
system defaults require `--scope system`. Review the resolved paths in the plan.
For `ssh-banner`, configure OpenSSH's `Banner` reference separately; this tool
does not edit `sshd_config` or reload the daemon. For an authenticated SSH dashboard,
use `--target shell --audience ssh` instead.

Setting `frequency = "interactive"` changes the shell guard, not the host's startup-file arrangement. For system-wide non-login interactive Bash sessions, explicitly choose a `--shell-file` that those sessions read. That integration is host-specific; the default `/etc/profile.d` hook alone does not provide it.

Generated console and SSH notices use deliberate public text, with no process inventory, session details, command hooks, or automatic collection at authentication time. Generation escapes literal backslashes for agetty's `issue` format. Imported static artifacts are treated as already serialized bytes and installed unchanged, so their existing agetty escapes or terminal controls retain their original meaning. Inspect an unfamiliar static file for its intended consumer; no normalization is promised for opaque imports.

Generic `text` is useful for another consumer but does not encode that consumer's
special substitutions. BusyBox/BSD gettys, PAM MOTD routes, Telnet services and
Windows sign-in notices require their own reviewed attachment. The
[surface matrix](compatibility.md#console-and-remote-routes) records what is
specified for later support.

Official references: [agetty manual](https://manpages.debian.org/trixie/util-linux/agetty.8.en.html) · [OpenSSH Banner](https://man.openbsd.org/sshd_config#Banner).

## Export on Windows, macOS or another generator host

Windows builds use create-only output automatically. Other hosts can select the same path with `--create-only`:

```sh
python3 motd.py build --preset workshop --shell powershell --design cards \
  --output ./workshop.ps1 --save-config ./workshop.toml --create-only
python3 motd.py build --preset home-lab --shell cmd --output ./home-lab.cmd --create-only
python3 motd.py build --preset public-console --target batch-text --output ./notice.cmd --create-only
```

Choose an existing directory you control and new destination names. The exporter refuses overwrites and `--replace`; it writes a final `.export.json` manifest containing hashes. On an ordinary failed write, it removes only files still matching the identity and bytes created by that attempt. A changed file is left for inspection. This is not managed installation, a crash-recovery journal, ACL backup or protection against hostile concurrent parent-directory replacement. A manifest's hashes identify content; they are not a signature or evidence that a login integration has been enabled.

On Windows, `py -3 motd.py ...` may be the appropriate Python launcher. Run the generated `.ps1` in the intended PowerShell or the generated `.cmd` in CMD; review the machine's existing execution policy and profile arrangement. This project does not silently change them. On macOS/BSD/other Unix hosts, attach generated output only through a startup route that is actually read on that host. See the compatibility guide for tested engines and pending integrations.

## Keep noninteractive sessions quiet

A terminal alone does not prove that a shell is interactive. The shell hook checks both interactive state and terminal output before displaying the dashboard, then applies the configured SSH filter. This matters for remote commands and file-transfer tools that rely on clean protocol streams.

Bash documents a special remote-shell case in which a noninteractive shell can read `.bashrc`. A hook in that file therefore needs its own guard. See [Bash startup files](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files).

This project does not need to modify PAM authentication behavior or disable the machine's existing MOTD globally. If another integration already displays similar information, decide explicitly which route should show it.

## Installing an existing output

Imports must be regular, non-hardlinked UTF-8 text files up to 2 MB. For a recognized project-generated shell output,
inspect its metadata and recovered configuration before installing or
reconfiguring it. Validate the recovered data; metadata is not permission to
execute arbitrary code. Static outputs carry no configuration metadata; retain
their TOML recipe or archived configuration.

Installing any existing executable output's exact bytes requires `--artifact FILE
--trust-artifact`, including files with recognized metadata. For an arbitrary
script, explicitly identify its interpreter and target. Inspection reads bytes
and reports a SHA-256 fingerprint; it does not execute the file to discover
settings. Opaque imports have no invented editable recipe: replace their artifact
or supply an explicit new recipe to change them.

Recognized generated recipes are rebuilt for preview, with hooks suppressed. An opaque script cannot supply a controlled demonstration: `preview --live --trust-artifact` explicitly executes its code and may produce its normal side effects. Inspection remains the nonexecuting action. Static imports are installed as serialized output bytes; use a recipe's `public_text` when generating a notice from literal text.

## Reconfigure, audit, repair, remove, restore

- **Reconfigure/upgrade** starts from saved or recovered configuration and generates a replacement for review. TOML output does not preserve the original comments or formatting.
- **Inspect/audit** compares available metadata, recorded paths, and file fingerprints without running the inspected script.
- **Repair** with `--name NAME` uses the complete current installation manifest, including files unchanged by upgrades and the current rollback lineage. It restores missing owned files and reports modified files without overwriting them.
- **Uninstall** selects an installation with `--name ID` and removes its managed integration while preserving unrelated content.
- **Rollback** creates an inverse of a completed transaction. It rejects later ownership changes or file drift that would make reversal unsafe.
- **Recover** reverses an interrupted apply toward its recorded before-state. It is not an ordinary rollback of an already completed installation.

For normal installation repair:

```sh
python3 motd.py repair --name home-lab
```

The older `repair --transaction ID` route remains available. Use `history` to find IDs for rollback and recover, which select `--transaction ID`. Recovery actions support `--yes` for explicit noninteractive application. User state is `${XDG_STATE_HOME:-$HOME/.local/state}/motd`; system state is `/var/lib/motd-wizard`; `--state-dir` overrides the location.

## Recovery boundaries

Recipe-based transactions archive the actual `config.toml`, generated output with
its appropriate suffix, a journal and binary before/after images. Opaque imports
retain output and fingerprints without a fabricated configuration. Restoration
preserves file bytes, mode, UID and GID. ACLs and extended attributes are not
preserved.

Each file replacement is atomic. A transaction involving several files is not one atomic operation; the journal records progress so interruption can be diagnosed and reversed. The configurator locks cooperating operations and checks for changed files, but cannot provide a universal compare-and-swap guarantee against a different program writing concurrently. Do not edit affected files while applying or recovering a transaction.

Transaction snapshots are limited to 16 MiB per managed file, checked before changes and during reads. Path names containing newlines or terminal control characters are refused before mutation. These bounds prevent accidental unbounded backups and ambiguous terminal plans; they do not make arbitrary destinations safe to take over.

The archive does not reverse external effects of user commands. A hook can change things outside the installer's ownership. Both preview modes suppress hooks for generated recipes; the explicit opaque-code execution described above has no such guarantee.

Keep the configuration and any desired standalone output separately if they must
survive deletion of the local transaction archive. No package repository,
automatic login-time updater or remote recovery service is needed.
