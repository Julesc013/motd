# Vendored Tomli 2.3.2

This directory preserves the upstream pure-Python parser and MIT licence from
[Tomli 2.3.2 on PyPI](https://pypi.org/project/tomli/2.3.2/). The release declares
Python 3.8 or newer and TOML 1.0 support. `provenance.json` records the official
source-distribution URL, its SHA-256 digest, and each retained file's digest.
The downloaded archive was checked against PyPI's published digest before use.

`tools/embed_toml.py` builds a plain Python factory at the end of `motd.py`.
It removes relative imports between the three parser modules and their duplicate
`__future__` directives, then indents their unchanged parser logic inside the
factory. It does not encode, evaluate or execute strings as Python. The factory
keeps upstream names out of the configurator's global namespace and is only
instantiated when the configurator lacks standard-library `tomllib`.

The complete licence is retained both here and as comments in the downloadable
configurator. No parser dependency or network access is needed when that file
runs. Generated MOTD scripts do not contain or need this Python parser.

The recipe contract remains TOML 1.0. The project uses 2.3.2 rather than Tomli
2.4+ because newer releases accept TOML 1.1, while Python 3.11's `tomllib`
implements the earlier format. Hand-written recipes should use the common
TOML 1.0 subset; generated recipes already do so.

## Updating

Fetch a deliberate upstream release, verify its archive, retain its licence and
record the new digests. Review parser changes, then run:

```sh
python3 tools/embed_toml.py
python3 tools/embed_toml.py --check
python3 -m unittest discover -s tests -p test_python_compatibility.py -v
```

Do not hand-edit the embedded copy. A parser update is a compatibility change;
it needs old-Python execution evidence and valid/invalid recipe checks.
