# Actual terminal PNG gallery

140 logical captures; 138 unique lossless PNGs.

Open [index.html](index.html) locally to filter by preset, interpreter, size, design, density, detail, theme, character set and colour mode.

The requested sizes are **40×25, 40×50, 80×25 and 80×50**. The full grid is preserved; no terminal output was cropped or resized to make a layout fit. The final row is reserved for the shell prompt.

Each record in [manifest.json](manifest.json) links its raw ANSI transcript, effective recipe, exact command, interpreter version, source hashes, cell geometry and lossless PNG pixel hash. Records may share a PNG when their actual output is identical.

Fixtures are synthetic. Configured before/after commands do not run. Static public notices have no invented colour/theme variants.

## Design comparisons

This bounded sampler has 120 structural comparisons (five designs × four sizes × two presets × three backends), 15 full-detail density contrasts, and five brief-detail views. Colors and character modes are covered by the separate 524-case classic gallery.

Density/detail contrasts use workshop/Bash at 80×50: all three densities at full detail, plus balanced/brief. The structural group supplies the balanced/normal reference. These are requested detail levels; actual row allocation still depends on available terminal space.

| Terminal | Five-design comparison |
|---|---|
| 40x25 | [Open PNG](comparisons/five-designs-40x25.png) |
| 40x50 | [Open PNG](comparisons/five-designs-40x50.png) |
| 80x25 | [Open PNG](comparisons/five-designs-80x25.png) |
| 80x50 | [Open PNG](comparisons/five-designs-80x50.png) |

Use the HTML filters for individual Bash, sh and PowerShell captures and their exact recipes.

