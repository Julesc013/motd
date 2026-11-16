# Installation and recovery

The configurator runs on Linux with Python 3.11 or later. The inherited dashboard requires Linux/procfs, Bash 4.3+, and GNU `timeout`, plus its enabled collectors' commands. Prelogin outputs are static text. Start the interactive workflow with `python3 motd.py`, or consult `python3 motd.py --help` for the command-line interface.

## Plan before applying

Select the action and destination, then review the plan. `plan` is read-only. `install` presents the plan and asks before applying it; `--yes` provides explicit noninteractive application. System scope requires root. Its files and ancestor directories must be root-owned and not writable by group or others; user-scoped installation should not require system privileges.

```sh
python3 motd.py plan --preset home-lab --target shell --scope user --audience all --name home-lab
python3 motd.py install --preset home-lab --target shell --scope user --audience all --name home-lab
```

Build, preview, plan, install, upgrade, and reconfigure accept a preset, a TOML configuration, or a recognized generated Bash artifact. Destination overrides include `--target`, `--scope`, `--audience`, `--name`, `--destination`, and `--shell-file`. `--state-dir` selects the transaction store. Use existing parent directories for output and installation paths; the tool creates its private state tree, not arbitrary destination directory trees.

An installation owns its recorded files or explicitly marked integration region. It does not acquire ownership of every MOTD, shell startup file, or SSH setting on the host. An unmanaged artifact destination requires `--replace` to take ownership with a backup, except for the `issue` target's explicitly planned replacement. Changed files and conflicting integrations must be made visible before replacement or removal.

## Target contracts

| Target and scope | Integration contract | Boundary |
|---|---|---|
| `shell`, user | Installs `~/.motd-ID.bash` and guarded managed blocks in `.bashrc` and the active Bash login file. The display requires an interactive shell and terminal output. | Bash only; noninteractive remote commands must remain quiet. `--audience all|ssh|local` filters eligible sessions. |
| `shell`, system | Installs `/usr/local/bin/motd-ID` and `/etc/profile.d/70-motd-ID.sh`. The display runs as the session user. | The default covers Bash login startup on hosts that read `/etc/profile.d`; it does not attach to every non-login interactive shell. |
| `issue` | Installs static public text; the system default is `/etc/issue`, with explicit backup/replacement. | agetty reads text, not Bash. Custom agetty options can select another file or disable issue display. |
| `ssh-banner` | Installs static public text; the system default is `/etc/ssh/motd-ID.banner`. | OpenSSH must reference that file through `Banner`. Installing the file is not proof that it is enabled. |

`ID` is the value of `--name`. Static user-scope installations require an explicit `--destination`; their standard system paths require `--scope system`. Overrides and planned integration edits appear in the plan. For `ssh-banner`, set the OpenSSH `Banner` reference separately; the configurator installs the text file, does not attach it to `sshd_config`, and does not reload the daemon. Verify the resulting route on the host. For an authenticated SSH dashboard, use `--target shell --audience ssh` instead.

Setting `frequency = "interactive"` changes the shell guard, not the host's startup-file arrangement. For system-wide non-login interactive Bash sessions, explicitly choose a `--shell-file` that those sessions read. That integration is host-specific; the default `/etc/profile.d` hook alone does not provide it.

Generated console and SSH notices use deliberate public text, with no process inventory, session details, command hooks, or automatic collection at authentication time. Generation escapes literal backslashes for agetty's `issue` format. Imported static artifacts are treated as already serialized bytes and installed unchanged, so their existing agetty escapes or terminal controls retain their original meaning. Inspect an unfamiliar static file for its intended consumer; no normalization is promised for opaque imports.

Official references: [agetty manual](https://manpages.debian.org/trixie/util-linux/agetty.8.en.html) · [OpenSSH Banner](https://man.openbsd.org/sshd_config#Banner).

## Keep noninteractive sessions quiet

A terminal alone does not prove that a shell is interactive. The shell hook checks both interactive state and terminal output before displaying the dashboard, then applies the configured SSH filter. This matters for remote commands and file-transfer tools that rely on clean protocol streams.

Bash documents a special remote-shell case in which a noninteractive shell can read `.bashrc`. A hook in that file therefore needs its own guard. See [Bash startup files](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files).

This project does not need to modify PAM authentication behavior or disable the machine's existing MOTD globally. If another integration already displays similar information, decide explicitly which route should show it.

## Installing an existing output

Imports must be UTF-8 text files. For a recognized project-generated Bash output, inspect its metadata and recovered configuration before installing or reconfiguring it. Validate the recovered data like any other configuration; metadata is not permission to execute arbitrary code. Static issue and SSH banner outputs carry no configuration metadata; use their TOML recipe or archived configuration.

Installing any existing Bash file's exact bytes requires `--artifact FILE --trust-artifact`, including files with recognized metadata. For an arbitrary Bash script, inspection reads bytes and reports the SHA-256 fingerprint. The configurator does not execute it to discover settings and does not claim it can reconstruct its author's configuration. Opaque imports have no archived editable recipe: replace their artifact or supply an explicit new recipe to change them.

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

Recipe-based transactions archive the actual `config.toml`, `output.bash` or `output.txt`, a journal, and binary before/after images. Opaque imports retain output and fingerprints without a fabricated configuration. Restoration preserves file bytes, mode, UID, and GID. ACLs and extended attributes are not preserved in v0.1.

Each file replacement is atomic. A transaction involving several files is not one atomic operation; the journal records progress so interruption can be diagnosed and reversed. The configurator locks cooperating operations and checks for changed files, but cannot provide a universal compare-and-swap guarantee against a different program writing concurrently. Do not edit affected files while applying or recovering a transaction.

The archive does not reverse external effects of user commands. A hook can change things outside the installer's ownership. Both preview modes suppress hooks for generated recipes; the explicit opaque-code execution described above has no such guarantee.

Keep the configuration and any desired standalone output separately if they must survive deletion of the local transaction archive. No package repository, automatic login-time updater, or remote recovery service is required by v0.1.
