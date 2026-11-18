# MOTD 0.5.0-alpha.1

This alpha replaces the default-Classic/customized-Classic split with a shared
presentation composer and replaces the default settings-page workflow with
guided choices that continuously preview actual generated output.

## Use it

Download the source ZIP, extract it, and run `python3 motd.py` on Linux/macOS or
`python motd.py` on Windows. Python 3.8 or later is required by the configurator.
The generated standalone scripts do not require Python on the destination.

Choose Create, a starting recipe, and the output interpreter. Number or arrow
keys update the preview immediately. Enter accepts, B goes back, and A opens
the relevant fine controls. Save the TOML recipe and build the standalone file.
The preview uses synthetic observations and suppresses configured hooks.

## Changes

- Named designs expand to shared layout policies. Classic can be customized as
  continuously framed sections, separate panels, open inventories, compact
  briefings or paired columns without selecting a separate renderer.
- Independent border family/visibility, heading style/alignment, separator
  summary/custom notes, full/short section labels, clipping policy and literal
  section titles/notes join the existing density/detail/palette/gauge controls.
- Compact Classic retains its useful service-state rows, CPU/memory/disk-I/O
  rankings and semantic colours. Geometry includes decoration and a prompt row.
- The wizard previews generated output in a cancellable process, caches
  completed previews and keeps input and resize handling responsive.
- `gallery/` groups compatibility, design presets, gauges, individual controls,
  combined recipes and a reproducible 64-image showcase. Presentation samples
  cover 80×25, 80×50, 120×50 and 160×50.
- The source-grounded EXT-IT review and shared presentation/observation contract
  document the architecture, lessons and boundaries of the current alpha.

## Verification and limits

Publication requires both repository verification workflows to succeed on the
exact main revision. The legacy workflow must execute its actual PowerShell 2
step; a skipped probe does not satisfy the release gate. The release assets
include a revision/file manifest and SHA256SUMS.

This is an alpha. The project does not claim every historical shell/OS pairing
is tested, or that terminal captures prove SSH/PAM/getty installation. The
compatibility guide records exercised engines and explicit gaps. Automatic
managed login installation remains Linux-specific; cross-platform generation
and create-only exports have their own documented boundaries.

The shared registry currently covers section text and presentation policy.
Typed observations, per-field units/severity/freshness and comprehensive
localization remain staged work in the specification. Unix display text retains
conservative sanitization; known single-cell terminal glyphs are supported,
while arbitrary Unicode text and emoji are not universally width-correct.

See [the integration report](project-review-2026-11-18.md),
[presentation contract](../specs/presentation-contract.md),
[gallery guide](gallery.md) and [compatibility](compatibility.md).
