# Build output

Build commands write standalone artifacts to an existing output directory.
Generated working files here are ignored by Git. Curated portable outputs live
in `examples/`; reusable human-readable recipes live in `presets/`.

`verification-v03-final.json` is the current complete local-suite record, with
its retained log in `verification-v03-final.log`. The corresponding
`verification-unix-current.json` and `verification-powershell-current.json`
record actual historical Unix and native PowerShell executions for the current
templates. `verification-v03.json` and the Unix/PowerShell legacy records retain
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
