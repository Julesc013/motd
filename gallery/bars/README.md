# Actual terminal PNG gallery

48 logical captures; 48 unique lossless PNGs.

Open [index.html](index.html) locally to filter by preset, interpreter, size, design, density, detail, theme, character set and colour mode.

The requested sizes are **40×25, 40×50, 80×25 and 80×50**. The full grid is preserved; no terminal output was cropped or resized to make a layout fit. The final row is reserved for the shell prompt.

Each record in [manifest.json](manifest.json) links its raw ANSI transcript, effective recipe, exact command, interpreter version, source hashes, cell geometry and lossless PNG pixel hash. Records may share a PNG when their actual output is identical.

Fixtures are synthetic. Configured before/after commands do not run. Static public notices have no invented colour/theme variants.

## Size comparisons

## Usage-bar comparisons

Wide bars occupy their available panel width. The numeric reading survives when the viewport is too short for an extra bar row. These layouts reuse the same observations; the memory/storage meaning remains backend-specific and explicitly labelled.

| Preset / backend | Design | Bars | Terminal | Preview |
|---|---|---|---|---|
| home-lab / bash | cards | inline | 40x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x25-cards-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal.toml) |
| home-lab / bash | cards | wide | 40x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x25-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / bash | dashboard | inline | 40x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x25-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal.toml) |
| home-lab / bash | dashboard | wide | 40x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x25-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / bash | cards | inline | 40x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x50-cards-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal.toml) |
| home-lab / bash | cards | wide | 40x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x50-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / bash | dashboard | inline | 40x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x50-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal.toml) |
| home-lab / bash | dashboard | wide | 40x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-40x50-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / bash | cards | inline | 80x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x25-cards-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal.toml) |
| home-lab / bash | cards | wide | 80x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x25-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / bash | dashboard | inline | 80x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x25-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal.toml) |
| home-lab / bash | dashboard | wide | 80x25 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x25-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / bash | cards | inline | 80x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x50-cards-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal.toml) |
| home-lab / bash | cards | wide | 80x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x50-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / bash | dashboard | inline | 80x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x50-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal.toml) |
| home-lab / bash | dashboard | wide | 80x50 | [PNG](png/home-lab-bash-cyan-unicode-colour-80x50-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-bash-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / sh | cards | inline | 40x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x25-cards-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal.toml) |
| home-lab / sh | cards | wide | 40x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x25-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / sh | dashboard | inline | 40x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x25-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal.toml) |
| home-lab / sh | dashboard | wide | 40x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x25-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / sh | cards | inline | 40x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x50-cards-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal.toml) |
| home-lab / sh | cards | wide | 40x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x50-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / sh | dashboard | inline | 40x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x50-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal.toml) |
| home-lab / sh | dashboard | wide | 40x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-40x50-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / sh | cards | inline | 80x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x25-cards-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal.toml) |
| home-lab / sh | cards | wide | 80x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x25-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / sh | dashboard | inline | 80x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x25-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal.toml) |
| home-lab / sh | dashboard | wide | 80x25 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x25-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / sh | cards | inline | 80x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x50-cards-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal.toml) |
| home-lab / sh | cards | wide | 80x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x50-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / sh | dashboard | inline | 80x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x50-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal.toml) |
| home-lab / sh | dashboard | wide | 80x50 | [PNG](png/home-lab-sh-cyan-unicode-colour-80x50-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-sh-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / powershell | cards | inline | 40x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x25-cards-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal.toml) |
| home-lab / powershell | cards | wide | 40x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x25-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / powershell | dashboard | inline | 40x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x25-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal.toml) |
| home-lab / powershell | dashboard | wide | 40x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x25-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / powershell | cards | inline | 40x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x50-cards-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal.toml) |
| home-lab / powershell | cards | wide | 40x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x50-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / powershell | dashboard | inline | 40x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x50-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal.toml) |
| home-lab / powershell | dashboard | wide | 40x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-40x50-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / powershell | cards | inline | 80x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x25-cards-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal.toml) |
| home-lab / powershell | cards | wide | 80x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x25-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / powershell | dashboard | inline | 80x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x25-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal.toml) |
| home-lab / powershell | dashboard | wide | 80x25 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x25-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal-bars-wide.toml) |
| home-lab / powershell | cards | inline | 80x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x50-cards-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal.toml) |
| home-lab / powershell | cards | wide | 80x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x50-cards-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-cards-balanced-normal-bars-wide.toml) |
| home-lab / powershell | dashboard | inline | 80x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x50-dashboard-balanced-normal.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal.toml) |
| home-lab / powershell | dashboard | wide | 80x50 | [PNG](png/home-lab-powershell-cyan-unicode-colour-80x50-dashboard-balanced-normal-bars-wide.png) · [Recipe](recipes/home-lab-powershell-cyan-dashboard-balanced-normal-bars-wide.toml) |
