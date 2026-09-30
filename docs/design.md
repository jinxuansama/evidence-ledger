# Design and manifest contract

The manifest is a JSON object with `version: 1`, `sources`, and `claims`.
IDs are unique within each list and contain ASCII letters, digits, `.`, `_`,
or `-`. Unknown optional metadata is preserved in the manifest but not audited.

| Object | Required fields | Meaning |
| --- | --- | --- |
| source | id, path, sha256 | Relative UTF-8 snapshot path and lowercase SHA-256 of exact bytes |
| fact claim | id, text, kind, source_id, quote | Non-empty statement and exact, non-empty excerpt |
| interpretation claim | fact fields plus rationale | kind is interpretation; rationale explains the inference |

Fact claims use `kind: "fact"`. IDs in `[[claim:ID]]` markers resolve against
claims, not sources. Duplicate IDs are malformed input. Invalid hashes,
unreadable files, changed snapshots, missing excerpts, unresolved references,
and malformed markers are audit errors. Unused ledger claims and drafts
without markers produce warnings. Excerpts match case and whitespace exactly.

Hashes bind to local bytes. The author chooses what source to capture and
records its digest; this does not prove that a publisher supplied those bytes.
A source URL, date, or rights note may be recorded as metadata but is not
independently verified. Snapshot paths are resolved before reading and must
remain under the manifest directory, including symlink targets.

Reports have an `ok` flag, counts, per-claim `provenance_ok`, referenced
claim IDs, structured issues, and a limitation statement. No network or
model calls occur. Text size is limited only by available memory; do not
process untrusted huge files with elevated permissions.

Tests deliberately include a false claim with a matching excerpt to show
why passing provenance checks cannot be advertised as fact verification.
