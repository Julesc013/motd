# MOTD integration and architecture review — 18 November 2026

## Outcome and evidence

The alpha consolidates default and customized rendering, replaces the normal
settings-page interaction with guided preview choices, and delivers organized,
reproducible galleries. The integration evidence for this work is retained in
[`build/alpha-20261118`](../build/alpha-20261118/); publication itself is gated on
the exact main commit, both CI workflows, actual PowerShell 2 execution and
verified release assets. See [release notes](release-0.5.0-alpha.1.md).

## Initial repository state

At the start of this review GitHub main was
[`ba908f7aaa8e76abe9827bf58f2f3d5f288de50f`](https://github.com/Julesc013/motd/commit/ba908f7aaa8e76abe9827bf58f2f3d5f288de50f).
There were no open pull requests or published releases. All four old feature
branch heads were ancestors of main. Re-merging those heads could not deliver
the newer implementation described in the supplied conversation transcript.

The published gallery had 524 compatibility captures, 140 design captures and
48 bar captures: 712 logical cases. Its size matrix covered 40×25, 40×50, 80×25
and 80×50. The 120×50/160×50 axis galleries described in the transcript were not
in the published repository or the available newer source trees.

An older local checkout held 810 changed/staged paths. Of their file objects,
687 already existed in the published Git history; 123 were different older
versions, chiefly generated copies, recipes, wizard images and metadata. The
entire checkout state was committed and published as
[`recovery/local-v04-20261118`](https://github.com/Julesc013/motd/tree/recovery/local-v04-20261118),
commit `45060a946a980e6ed3600a0887af95646d3f1c91`, with its complete tree verified
against the local snapshot. It is retained as historical recovery evidence;
its old generated outputs do not replace newer canonical runtime sources.

The unpublished newer renderer/wizard source described by the transcript could
not be recovered from the available files. This integration implements and
verifies those changes against the actual published baseline. Progress narration
and uploaded Git blobs without a reachable branch are not delivery evidence.

## Defects and causes

### 1. Cosmetic settings selected a different renderer

Default Classic had a compatibility rendering route. Changed presentation
settings entered the shared alternative route. This made an apparently cosmetic
change affect headers, row allocation, information density and inline colours.
The alternative Unix capture path stripped semantic styling.

The correction is structural: all presentations resolve settings and run through
one section planner/composer per runtime family. The existing collection and
section-data adapters remain in use. No default-value test chooses a separate
Classic renderer. Named designs expand to policy values; explicit low-level
settings override only their corresponding properties.

Visual review caught a temporary regression in the first consolidation: block
gauges became ASCII marks and 80×25 lost useful service and process rows. The
shared sanitizer now retains the known one-cell terminal glyphs, while compact
allocation preserves Classic's useful summaries and rankings. Regression tests
exercise default, customized and preset-equivalent output.

### 2. The wizard made users navigate configuration instead of evaluate choices

The prior settings pages mixed arrangement, detail and low-level controls. A
preview required an extra action, and synchronous preview work could delay input.
The replacement asks a high-level decision at a time, previews immediately on
selection, and offers relevant fine controls with A. Enter accepts; B returns,
including from the first fine-controls page. Visiting a decision does not erase
explicit settings.

The preview executes a generated script using synthetic data with hooks disabled.
It runs in a cancellable child, caches completed results, labels the prior frame
while updating, and rejects obsolete results. Resize and cancellation remain
responsive. A line interface remains available on limited terminals.

### 3. “Finished locally” did not mean usable from main

The earlier work accumulated generated assets and evidence before publishing a
reachable commit. This left the user's clone behind the narrated progress.
This work uses small local commits, publishes task checkpoints through the
connected repository interface, and retains a recovery branch. The final
integration must be verified on its published revision, not an earlier checkpoint.

The release workflow first creates an owned draft, uploads all assets, verifies
names/sizes/SHA-256 values and then publishes. Interrupted uploads remain drafts;
reruns resume only the matching draft. Existing tags are never moved. Main and
tag identity are re-read before publication. GitHub offers no transaction across
all those objects, so the implementation detects concurrent changes rather than
claiming global atomicity.

## Customization delivered

The configurable axes are arrangement, frame grouping, border family and
visibility, heading style/alignment, separator summaries or custom notes,
full/short section labels, overflow, padding, gaps, density, detail, palette,
colour emphasis, character set, inline/wide gauges, visible sections, their
order/priority and per-section detail. Titles and notes are literal text.

Five named designs are presets of shared policy. The combined gallery deliberately
keeps `design = "classic"` and changes explicit settings, demonstrating that
open inventories, separate cards, paired panels and briefings are compositions
of the same engine. Columns reflow below 80 cells. Independent columns resolve
a continuous frame to separate panels; that is a documented geometry constraint.

[`gallery/`](../gallery/README.md) groups compatibility, designs, gauges,
individual axes, compositions and the seeded showcase. Axis/composition captures
use 80×25, 80×50, 120×50 and 160×50. They retain the complete terminal grid and
prompt row, exact recipe, ANSI transcript, source hashes, interpreter identity
and decoded image hash. Thumbnail contact sheets are explicitly reduced views;
the full captures are never cropped or scaled to conceal overflow.

## What should share a definition next

| Contract | Purpose | Current boundary |
|---|---|---|
| Field definition | Stable ID, type, unit, full/short labels, formatting and localization keys | Shared section labels exist; per-field registry remains to implement |
| Observation | Separate valid zero from unavailable, denied, timeout, partial and stale values | Existing adapters retain their documented metrics and gaps |
| Units and numeric formatting | Consistent binary/decimal scales, precision, ratios, rates and rounding | Some formatting remains backend-specific |
| Severity and palette roles | One semantic status, independent colour mappings and plain-text markers | Existing semantic colours preserved; complete typed severity model remains staged |
| Text width and overflow | Safe literal strings, glyph capabilities, bounded clipping | Known glyphs supported; arbitrary Unicode/grapheme width is not universal |
| Retention | Useful minima, priority, detail alternatives and truthful omissions | Shared planners and regression coverage delivered |
| Collection capability/budget | One bounded snapshot, provenance, coverage and cancellation | OS-specific providers remain explicit; no claim all old systems are supported |
| Config state and preset expansion | Distinguish auto/inherited/explicit/empty choices | Shared policies and draft-preservation tests delivered |
| Export/install lifecycle | Distinguish generation, validation, installation and activation | Existing journal/create-only boundaries retained |
| Evidence | Link source, recipe, runtime, terminal bytes and image | Source-bound gallery manifests and release checks delivered |

The detailed contract is in [the specification](../specs/presentation-contract.md).
The next implementation should introduce typed observations incrementally at
collector/formatter boundaries, preserving current behavior with targeted parity
checks. Another parallel theme implementation would recreate the current failure.

## EXT-IT/motd review

The reference was audited at commit
[`dbeb19c974c09b6c123f85213934988c11119046`](https://github.com/EXT-IT/motd/commit/dbeb19c974c09b6c123f85213934988c11119046).
Its readable identity/summary/detail hierarchy and shared deployed runtime are
useful patterns. Its current runtime uses fixed 42-cell bars and no terminal row
planner; several failed observations become healthy-looking zero values, and
individual timeouts do not create a total collection deadline. The standalone
and Salt installation paths also differ in activation-failure handling.

The supplied 11 C1/input checks and six public-IP opt-out checks passed. Isolated
source-fragment checks reproduced an overlong bar for 150/100 usage and literal
backslash escape interpretation through `printf %b`. These are bounded findings,
not claims of a demonstrated live exploit. See [the full source-linked review](reference-ext-it-review-2026-11-18.md).

## Practical limits

This alpha does not establish every historical interpreter/OS combination,
Windows interactive console behavior, or real SSH/PAM/getty deployment. Native
CI execution and local evidence must be read separately from syntax targets.
Automatic managed installation remains Linux-specific. Generated scripts can be
exported for other supported interpreters without changing the development host's
login configuration. No user hooks run during gallery or wizard capture.

The main usability correction is delivered without restarting in another language.
Python remains the portable configurator; generated scripts remain standalone.
A full typed field/observation layer and comprehensive localization are the next
architectural work, not an implied property of this alpha.
