# Build output

Build commands write standalone artifacts to an existing output directory.
Generated working files here are ignored by Git. Curated portable outputs live
in `examples/`; reusable human-readable recipes live in `presets/`.

The current continuation is indexed by
[`verification-review-20261117.json`](verification-review-20261117.json).
It pins source/test hashes, local results, actual Python3.8 and additional Unix
execution, exact PowerShell6/7 artifact lineage, three galleries, and native CI.
[`review-20261117/file-map.json`](review-20261117/file-map.json) maps the original
verification environment's paths to retained files and hashes. Raw logs, XML,
runtime-download provenance and the environment-specific replay script are
preserved there. Counts describe their named checks; they must not be added
together as independent test coverage or applied to another source revision.

The final implementation at `0f16e88` passed both native workflows (nine jobs).
The [native PowerShell record](review-20261117/native-ci-0f16e88/evidence.json)
includes actual PS2.0 probe/XML and ten generated-artifact hash comparisons;
the [Verify record](review-20261117/native-ci-0f16e88/verify-summary.json) includes
the Linux, Python 3.8, macOS and Windows jobs. Their raw files are retained in the
same directory. The sibling `native-ci-9cefbdd` directory preserves the initial
macOS test-assumption failure and successful jobs from the preceding run.

The records below are historical stages and retain their original scope.

The version0.4 records are `verification-v04.json` and its retained log,
`verification-python38-v04.json` with its log, `verification-unix-v04.json`,
`verification-powershell-v04.json`, and `verification-native-v04.json`. They
identify exact sources, test commands, native engines, host versions and skips.
The native record links to Windows/macOS CI and the actual PowerShell2 XML
evidence; a version request without an exact-engine assertion is not a pass.
The gallery manifests under `examples/gallery/` and `examples/designs/` retain
their own capture, transcript, grid, source and decoded-pixel evidence.

`verification-v03-final.json` and `verification-v03-final.log` are the complete
version0.3 local-suite record. The historically named
`verification-unix-current.json` and `verification-powershell-current.json`
refer to that earlier release, not automatically to the latest templates.
`verification-v03.json` and the Unix/PowerShell legacy records retain
the preceding development checks, exact engine versions, source provenance,
build qualifications and remaining unverified targets. Revision-specific CI
adds native Windows and macOS evidence; a local Linux test cannot establish that.

`verification-runtime.json` is a historical bounded test record from this development
environment, not a production-host benchmark or a claim of universal support.
`verification.json` records the earlier complete test run and pins its tested source
and test files by SHA-256. CI results provide subsequent revision-specific checks.

`verification-bash32.json` records the **v0.2** unsupported-dashboard guard and
native sh fallback under an actual Bash 3.2 build. Version0.3 supersedes that
behavior with automatic dispatch. `verification-bash43.json` exercises the earlier
full renderer's minimum shell version on current Linux. Neither certifies a
historical OS. Native Windows PowerShell coverage is recorded by the Windows
CI jobs; a Linux `pwsh` test is a separate environment.
