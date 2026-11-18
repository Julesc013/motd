# EXT-IT/motd source review — 18 November 2026

## Scope and conclusion

Reviewed upstream main at [`dbeb19c974c09b6c123f85213934988c11119046`](https://github.com/EXT-IT/motd/commit/dbeb19c974c09b6c123f85213934988c11119046), authored 14 April 2026. This review read the runtime, installer, Salt states and two supplied test scripts. Source inspection, executed checks and proposed requirements are distinguished below. No installation or service reload was performed.

The reference is a useful Linux administration dashboard. Its hierarchy, selective detail and shared runtime deployment are worth adopting as ideas. Its fixed geometry, presentation-dependent data strings and incomplete failure reporting are unsuitable as the foundation of this project's universal adaptive engine.

## Evidence and lessons

Source links below are pinned to the reviewed revision.

| Source-level fact | Assessment and requirement for this project |
| --- | --- |
| Standalone `install.sh` obtains `motd/10-system-info.sh`; Salt deploys that same file without runtime Jinja. | A sound separation: maintain canonical runtime sources and generate distribution copies. Export and installation adapters must not fork the renderer. [Installer][installer], [Salt MOTD][salt-motd]. |
| The output separates identity, aligned observations, resource bars, services and security detail. | Preserve this visual hierarchy using independently resolved layout, density, detail, heading and gauge settings. The named design should only be a preset. [Runtime][runtime]. |
| Dynamic service discovery batches its discovered unit list into one `systemctl is-active` call; Docker obtains one container snapshot. | Reuse one collected snapshot for overview and detail. Other service probes are separate; do not describe all collection as one batched call. [Runtime][runtime]. |
| Bars default to 42 cells, labels use a 16-character pad, branding determines header width, and the output has no terminal row planner. | Every widget must render within an allocated cell rectangle; headings, frames, notes and gaps consume measured space. [Runtime][runtime]. |
| Missing update information can produce “Up to date”; failed jail count parsing becomes zero; failed anomaly output can produce “no anomalies”; failed Docker output after a successful service-state check becomes zero containers. | A successfully observed zero is distinct from unsupported, denied, timed out, failed, partial or stale data. Presentation cannot improve a failed observation into a healthy result. [Runtime][runtime]. |
| Probes use serial per-command timeouts, with per-jail loops and a five-second APT fallback. Hostname and disk queries are not all timeout-wrapped. | Individual timeouts do not establish a total login deadline. Use one overall budget, bounded work and explicit partial results. [Runtime][runtime]. |
| The disk collector enumerates mounts and invokes `df` again per candidate. | Parse a bounded filesystem snapshot once and derive totals, ranking and detail from it. [Runtime][runtime]. |
| Installer and Salt contain substantial separate validation/default/configuration code despite their shared runtime. | A shared configuration file format alone is insufficient. Define canonical enums, defaults, bounds and preset policies, and check generated adapters for agreement. [Installer][installer], [Salt MOTD][salt-motd], [Salt banner][salt-banner]. |
| The standalone installer returns failure when an active SSH service fails to reload. Both Salt reload commands end in `|| true`. Salt also writes the live drop-in before validating it, while standalone validates a temporary candidate first. | Distinguish staging, validation, installation and activation. File existence or a successful state run does not prove activation. This project does not silently reload services. [Installer][installer], [Salt MOTD][salt-motd], [Salt banner][salt-banner]. |
| The runtime exits when stdout is not a TTY; Salt installs an interactive `profile.d` wrapper as its actual display route. | Test each login adapter explicitly. A PTY render is not evidence of SSH/PAM/getty installation. [Runtime][runtime], [Salt MOTD][salt-motd]. |

## Executed verification

On the available Linux host, using the pinned source files:

- `bash tests/test_c1_injection.sh`: **11/11 checks passed**. These drive installer dry-run validation; no real login files were changed.
- `bash tests/test_pubip_optout.sh`: **6/6 checks passed**. Explicit empty public-IP settings remain empty rather than reactivating a default endpoint.
- Isolated upstream `bar` function with `used=150`, `total=100`, `width=42`: **63 visible cells**. This proves an out-of-range input overflow, not that normal live measurements routinely trigger it.
- Isolated provider-text output expression using `printf '%b\n'`: literal `X\033[31mY` becomes an actual ESC sequence. The source comments claiming that `%b` does not interpret interpolated payload escapes are incorrect. This establishes a formatting failure mode, not an externally exploitable attack path. Emit literal provider text with `%s` and trusted styling separately.

The locale probe also matches exact `C.UTF-8`, while this host's locale inventory spells it `C.utf8`. The secondary `en_US` probe works on this host. A system with only `C.utf8` can fall back to byte-counting `C`; this latter outcome is a source-derived inference. Codepoint count also differs from terminal cell width for CJK and combining characters. The installer explicitly documents its CJK limitation and rejects supplementary-plane characters instead of implementing a general width model.

[Upstream CI][ci] runs shell/YAML lint and the two narrow suites above. These passes establish neither adaptive geometry nor cross-platform capability coverage, provider-failure correctness, or installer/Salt parity.

## Architecture lessons for this project

The highest-value shared definitions are stable field identity, typed value/unit, availability, freshness, provenance, severity, literal text, display-cell width, retention priority and provider capability. See [the presentation contract](../specs/presentation-contract.md).

Our baseline also had a separate unchanged-Classic path in PowerShell and design branches in resource sizing and rendering. A cosmetic change could therefore change allocation and header structure. The current consolidation replaces these choices with resolved policy data and a common panel composer. This removes a specific source of presentation drift; it does not by itself create a fully shared observation model across Bash, portable Unix and PowerShell.

Keep backend adapters where operating-system APIs differ. Share semantic contracts and fixtures across those adapters. Do not add an unbounded plugin framework, a background daemon, or a single cross-platform collector pretending that unavailable APIs exist.

[runtime]: https://github.com/EXT-IT/motd/blob/dbeb19c974c09b6c123f85213934988c11119046/motd/10-system-info.sh
[installer]: https://github.com/EXT-IT/motd/blob/dbeb19c974c09b6c123f85213934988c11119046/install.sh
[salt-motd]: https://github.com/EXT-IT/motd/blob/dbeb19c974c09b6c123f85213934988c11119046/salt/motd.sls
[salt-banner]: https://github.com/EXT-IT/motd/blob/dbeb19c974c09b6c123f85213934988c11119046/salt/banner.sls
[ci]: https://github.com/EXT-IT/motd/blob/dbeb19c974c09b6c123f85213934988c11119046/.github/workflows/ci.yml
