# Build output

Build commands write standalone artifacts to an existing output directory.
Generated working files here are ignored by Git. Curated portable outputs live
in `examples/`; reusable human-readable recipes live in `presets/`.

`verification-runtime.json` is a bounded test record from this development
environment, not a production-host benchmark or a claim of universal support.
`verification.json` records the complete test run and pins the tested source
and test files by SHA-256. CI results provide subsequent revision-specific checks.
