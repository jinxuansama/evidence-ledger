# Evidence Ledger

**An offline audit trail for research claims and source snapshots.**

[中文说明](README.zh-CN.md) · [Design and schema](docs/design.md) · [Contributing](CONTRIBUTING.md)

Evidence Ledger checks that a cited local source has not changed, that a
recorded excerpt exists verbatim, and that explicit claim references in a
Markdown draft resolve to the ledger. It separates declared facts from
interpretations, which require a written rationale.

A passing audit establishes provenance consistency. It **does not verify
truth or whether an excerpt actually supports a claim**. Unmarked statements
in a draft are outside the audit. This distinction is explicit in every report.

## Quick start

Python 3.10+; no runtime dependencies, model credentials, or network calls.
From a clone of this repository:

```sh
python -m pip install .
evidence-ledger audit examples/ledger.json --draft examples/draft.md
evidence-ledger audit examples/ledger.json --draft examples/draft.md --format markdown
evidence-ledger hash examples/source.txt
python -m unittest discover -s tests -v
```

The included example is synthetic. Expected result: `ok: true`, one source
snapshot, two referenced claims, no issues.
Edit `examples/source.txt` and rerun: `hash_mismatch` fails the audit even
when a previously cited excerpt is still present. Refresh hashes only after
deliberately reviewing the changed source.

## Use in your workflow

Save a permitted source as UTF-8 text. Record its digest with the `hash`
command and add an exact excerpt to `ledger.json`. Add a `[[claim:ID]]`
marker to your draft. Commit the source, manifest, and draft together when
you have redistribution rights; otherwise keep the source locally.

```python
from evidence_ledger.core import audit
report = audit("examples/ledger.json", "examples/draft.md")
assert report["ok"]
```

JSON and Markdown reports are deterministic for the same inputs. CLI exit
codes are 0 for passing provenance checks, 1 for audit failures, and 2 for
invalid input or I/O errors. Warnings do not change a passing exit code.
`--output report.json` writes a report to an existing directory.

## Scope and maturity

Initial version 0.1.0. Supports UTF-8 text snapshots, not PDF parsing, web
retrieval, semantic verification, or bibliography formatting. Paths cannot
escape the manifest directory, including through symlinks. The ledger may
still contain a wrong interpretation or false source; human review is needed.
MIT licenses this software and the original examples, not third-party sources.

AI assisted implementation and test development. No institutional endorsement
or community adoption is claimed. See [the roadmap](docs/roadmap.md).
