# Shared presentation and observation contract

Status: **implementation contract and staged architectural target**, 18 November 2026.

This document distinguishes the presentation controls being consolidated for the alpha from deeper field-level contracts that still require implementation. A requirement below is not evidence that a particular operating system or historical interpreter has passed it. Exact source revisions, engine versions, test outcomes and skips belong in release evidence.

## 1. Product and source boundaries

One Python configurator reads and validates a portable recipe, resolves presets and produces standalone programs. Canonical backend templates implement the required interpreter/OS adapters. Generated embedded copies and examples are checked outputs, not additional source trees to maintain manually.

“One engine” means one resolved presentation model and one composition path per supported backend, with shared policy definitions and semantic tests. It does not mean Linux `/proc`, Windows APIs and historical shell syntax can be implemented by one interchangeable system-call provider. Platform adapters remain explicit.

A design name is input to preset expansion. Once resolved, layout and rendering consume the resulting properties. No fast path may select a second renderer merely because all settings have default values. A palette, border, label or heading change must not secretly replace the layout or discard unrelated overrides.

## 2. Delivered presentation controls and resolution

The current consolidation implements these recipe controls and corresponding native presentation behavior. Release evidence must establish each backend separately.

| Axis | Values / contract |
| --- | --- |
| `panel_layout` | `auto`, `stack`, `columns` |
| `panel_frame` | `auto`, `continuous`, `separate`, `none` |
| `heading_style` | `auto`, `rule`, `plain`, `inline`, `hidden` |
| `border_style` | `single`, `rounded`, `double`, `heavy`, `ascii` |
| `border_visibility` | `all`, `outer`, `sections`, `none` |
| `heading_align` | `left`, `center`, `right` |
| `separator_text` | `none`, `summary`, `custom` |
| `label_style` | `full`, `short` |
| `overflow` | `ellipsis`, `clip` |
| `section_titles`, `section_notes` | Known section IDs mapped to literal strings, at most 120 characters each |
| Existing independent controls | Density, detail, padding, section gap, colour emphasis, bar layout, section selection/order/priority and section detail |

Preset policies are data:

| Preset | Arrangement | Frame | Headings |
| --- | --- | --- | --- |
| Classic | Stack | Continuous | Rule |
| Cards | Stack | Separate | Rule |
| Dashboard | Columns | Separate | Rule |
| Ledger | Stack | None | Inline |
| Briefing | Stack | None | Plain |

The default border style is double, default separator text is the observation summary, and full labels retain the Classic uppercase section names.

Explicit low-level settings override corresponding preset defaults. `auto` inherits a preset property; it is not an instruction to reset the entire draft. Columns reflow to a stack below 80 columns. At a width permitting columns, a continuous-frame request resolves to separate frames, because this implementation composes independent panels. That resolution must be visible in inspection/preview and consistent across backends.

Border visibility distinguishes outside frames from section rules. Heading text survives disabling border glyphs unless heading style itself is hidden. ASCII output overrides Unicode border/gauge glyph selections. Separator metadata remains optional: disabling it retains its numeric observations in the body. An exact duplicated first observation may move into its heading only when the complete summary fits; a clipped heading cannot replace that observation. Custom notes and headings are literal text, never shell expressions.

The shared section-label registry centralizes full and short section captions. It does **not** yet centralize every field label, value formatter or translated string.

## 3. Next shared field and observation model

The following are **target contracts**, not a claim that all existing collectors already emit this model.

A field definition has a stable ID independent of its localized label, value type, canonical unit, full and short label keys, formatting policy, severity policy, visibility/retention priority and supported provider capabilities. Display labels must never be database keys or identifiers used to match observations.

An observation contains a typed value plus:

- Availability: available, unsupported, denied, timed out, error, or partial.
- Provider identity and relevant scope/coverage, such as readable processes out of sampled processes.
- Capture time, interval when applicable, and freshness state or maximum age.
- Canonical unit and distinction between a counter, gauge, rate, ratio and enumeration.
- Severity determined from validated values and policy, independently of palette.

Unavailable values do not become zero. A true empty set is distinguishable from a failed query. An observed counter is not a rate unless a valid sampling interval and two compatible observations exist. Unknown or stale data must remain recognizable in plain or monochrome output.

Units and formatting are centralized policy: bytes versus bits, binary versus decimal scale, precision, rounding and interval labels must be explicit. Rounding affects display only; thresholds and sorting use validated original values. Resource ratios reject invalid totals and preserve unavailable state; decorative fill is bounded by its allocated cells.

Freshness belongs to the observation. A cached value retains its original capture timestamp. Refreshing a preview or reusing a cached result cannot make old data appear newly observed.

## 4. Text and colour

A literal-text layer sanitizes control sequences before measuring or displaying external data. Trusted style tokens are distinct from text. Implementations must not decode backslash escapes, evaluate expressions or interpret provider strings as format strings. Unicode sanitization works on valid codepoints without deleting continuation bytes from otherwise valid UTF-8.

Display width is measured in terminal cells, excluding trusted styling. Combining marks, wide characters and surrogate pairs must not cause wrapping or split characters. This is a target contract for arbitrary localized text. The current Unix body sanitizer supports conservative ASCII text and an explicit set of known single-cell terminal glyphs; other Unicode text can be replaced. Python/PowerShell width handling also has terminal-dependent limits for joined emoji. This alpha does not provide a complete universal grapheme-width implementation. Explicit ASCII fallback is a supported capability decision.

Palette roles include normal, muted, accent, good, warning and future error/unknown roles. Information severity and colour emphasis are separate. A different palette must preserve observation meaning, thresholds, numeric content and retention decisions. At constrained widths, full/short labels use registered alternatives; arbitrary commands, service names and user text are not rewritten by global abbreviation replacements.

## 5. Layout and omission

Planning precedes output. The planner accounts for the title, host context, headings, notes, outside/section borders, padding, column gutters, gaps, retained body rows and omission footer. At 25 rows or fewer, every layout combines demo provenance, host context and title into one header row, with provenance and host context first so a long title cannot hide them. Larger views retain a separate context row. The last terminal row remains available for the shell prompt. Clipping pixels or discarding overflowing lines after rendering is not a valid fit strategy.

Content has useful minimum representations. Resources retain labelled numeric summaries; process summaries retain CPU, memory and disk-I/O leaders, and the separate disk-I/O section retains its measured leader when selected. Optional detail is reduced before complete sections are removed. Explicit priority controls scarce-space retention. Every omitted configured section is identifiable in a bounded footer; hidden detail must not be described as hidden sections.

Density governs whitespace; detail governs information. Changing density may consume more of a fixed viewport, but must not silently change the requested detail setting. Cosmetic border-glyph changes have identical allocation costs and must retain the same observations. Changes that add real rows, such as headings or custom notes, legitimately affect allocation and must be demonstrated by the gallery.

## 6. Collection, preview and capabilities

Target collection contract: one bounded snapshot per live render, with cached/batched reads shared across summaries and details. A total deadline bounds work in addition to individual command timeouts. Cancellation terminates and reaps subprocesses; stale queued previews cannot overwrite newer selections. Provider failure produces an explicit observation state and does not execute additional unbounded fallbacks.

The wizard uses synthetic observations by default and never executes configured hooks during preview. Selection updates the draft and preview without writing installation files. High-level guided choices are the normal route; fine controls remain available at the relevant step and preserve unrelated settings. A low-capability line-mode interface remains usable.

Provider capability is separate from interpreter syntax and terminal capabilities. Report tested engine/OS combinations, unverified syntax targets, unavailable metrics and login-adapter coverage separately. A modern PowerShell Linux pass does not certify Windows PowerShell 2, and a dash pass does not certify historical Bourne shells. No network request, package installation or privilege escalation is implied by displaying the MOTD.

## 7. Export, installation and release evidence

Generation, validation, export, installation and activation are separate lifecycle states. A generated artifact carries its recipe/revision provenance where supported. Import inspection never executes arbitrary input to discover its configuration. File hashes provide integrity evidence, not publisher authentication.

Create-only cross-platform export keeps its narrower contract. Managed installation uses the existing ownership/journal boundaries and preserves unrelated startup text. Multiple file updates are not described as a globally atomic transaction. Automatic service reloads remain outside this project's implicit behavior.

A gallery case records resolved recipe, synthetic scenario, terminal geometry, interpreter, captured transcript, source digest and PNG digest. Images must come from real terminal output, fit the declared grid without scroll/wrap, and retain decoded pixels under lossless compression. Single-axis comparisons hold other inputs fixed; combined recipes are labeled separately. The required review sizes are 80×25, 80×50, 120×50 and 160×50, with smaller hostile cases retained for regression checks.

Before a release is described as ready, evidence must follow the exact published source and distinguish passed, failed, skipped and unexecuted checks. A large gallery count is not a substitute for native backend, interaction, data-correctness or lifecycle tests.
