# Actual-terminal PNG gallery

The gallery captures generated scripts in real pseudo-terminals at **40×25,
40×50, 80×25 and 80×50**. Width and row arguments are supplied to the renderer,
and the PTY itself has the same dimensions. The capture is then decoded as
terminal cells. Output that would wrap, overwrite the reserved prompt row, scroll
the screen or use an unknown terminal control is rejected; it is not cropped
into a plausible-looking picture.

## Matrix and retained evidence

The shell matrix is two presets (workshop and home-lab), four outputs (Bash, Zsh,
portable sh and PowerShell), four themes (cyan, green, amber, mono), ASCII and
Unicode, colour and plain, and the four requested sizes: **512 logical captures**.
Public static outputs also have four-size captures. They do not receive invented
theme variants that their text format does not implement.

Every logical case retains an ANSI transcript, its effective TOML recipe,
interpreter identity, exact command, generated-source hash, terminal-cell hash,
geometry and PNG pixel hash in the gallery manifest. Identical pictures share a
PNG while retaining their separate records. This prevents the Zsh launcher and
plain/monochrome equivalents from multiplying identical image files.

The fixtures are populated synthetic examples. They are labelled as such and do
not claim to show a real machine's workload. Before/after hooks are suppressed.
The `.sh` examples show the portable Unix branch also used on older Bash and
systems without the full Linux renderer's capabilities. The captured interpreter
and host are always recorded; a PNG is not proof that an old OS was tested.

## Resolution and compression

Rendering uses an installed DejaVu Sans Mono font at 30 pixels, a consistent
two-times display scale, and a full terminal grid including blank unused rows.
The font variants' SHA-256 hashes, family/face/version, Pillow/wcwidth versions,
cell dimensions, colour palette and output dimensions are recorded. The font is not bundled; its licence is
available from the [DejaVu project](https://dejavu-fonts.github.io/License.html).

PNG encoding uses Pillow's lossless level-9 compression. When supplied, oxipng
tests stronger lossless encodings with maximum optimization and a bounded
compression budget. Optional Zopfli performs additional compression work. No
palette approximation, lossy colour quantization, resolution reduction or
transparent-pixel alteration is allowed. Every optimized image is decoded and
its RGBA pixels compared with the original raster.

“Lossless” means every decoded pixel is unchanged. It does not mean a file can
be compressed by 100%, or that one can prove the smallest possible PNG encoding.
The manifest records actual before/after sizes and the optimizer used.
Capture and pixel deduplication finish before compression starts. Four independent
PNG optimizers then run concurrently by default, each using at most two threads;
`--jobs` adjusts this limit. The full gallery selects oxipng's `max` strategy set,
fast filter evaluation and libdeflate, with a 30-second optimization budget per
file. These exact options are recorded; they do not imply an exhaustive search
of every PNG encoding.

Four-size comparison sheets paste the original PNGs at their native pixel size;
they do not rescale the 40-column and 80-column captures to equal widths.

## Rebuild

The configurator and generated scripts do not acquire these dependencies. The
developer gallery tool needs Pillow, wcwidth, the selected output interpreters,
the installed monospace font and optional [oxipng](https://github.com/oxipng/oxipng).
The build and verification tool runs on a POSIX host; it uses POSIX PTYs and
`TIOCSWINSZ`. The PNGs and local HTML index can be viewed on any platform.

```sh
python3 tools/build_gallery.py \
  --powershell /path/to/pwsh \
  --optimizer /path/to/oxipng \
  --opt-level max \
  --zip /existing/directory/motd-gallery.zip
```

Add `--zopfli` for a slower five-iteration lossless pass. Benchmark it on a small
selection before rebuilding the full matrix:

```sh
python3 tools/build_gallery.py \
  --output /existing/directory/gallery-smoke \
  --presets workshop --shells bash --themes cyan \
  --charsets ascii --colours colour --sizes 40x25 \
  --no-static --no-comparisons
```

Open `examples/gallery/index.html` locally for the filterable index, or follow the
PNG/transcript links in `examples/gallery/README.md`. The archive extracts into
`examples/gallery/` relative to a repository root. Each raw transcript remains
available for independent inspection and re-rendering.

## Wizard resize examples

The separate `examples/wizard-40x25.png`, `wizard-40x50.png`,
`wizard-80x25.png` and `wizard-80x50.png` images use the live wizard's own frame
function. Each shows the same theme-selection page with ten fixed control rows;
the remaining 15 or 40 rows are passed to the adaptive MOTD preview. They retain
the complete terminal grid and skip configured calls. The matching `.ansi`
files and `wizard-manifest.json` retain source, transcript, cell and pixel hashes.
The additional `wizard-call-samples-80x50.png` shows the optional Fastfetch and
after-call sample view. Its call output is display-only demonstration text;
the configured commands are never executed to produce the picture.

```sh
python3 tools/build_examples.py --png --optimizer /path/to/oxipng
```

Without `--png`, the example builder keeps the normal text/SVG workflow and
does not require Pillow, wcwidth or a particular installed raster font.

## Verify retained evidence

```sh
python3 tools/build_gallery.py --verify --require-full
```

This checks the complete 524-case matrix, repository source hashes, every recipe
and regenerated artifact hash, raw transcript hashes, terminal-cell geometry,
all unique PNGs' file hashes and decoded RGBA hashes, and the comparison sheets.
It never executes a generated script or hook, installs anything, or needs the
native interpreters or optimizer. Omit `--require-full` when verifying a deliberately
smaller matrix. Source changes invalidate the recorded build; recapture from the
changed source before claiming the images demonstrate that version.
