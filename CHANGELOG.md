# Changelog

## Unreleased

- Reject duplicate JSON member names at every level of a manifest before
  auditing; repeated fields can no longer silently replace sources or claims.
- Report unresolvable source paths and symlink loops as `unsafe_path` audit
  issues instead of aborting the report; reject embedded null characters.
  Continue checking other sources and preserve normal in-directory symlinks.
- Add regression coverage for loop failures, CLI audit-failure output,
  embedded null characters, and valid in-directory symlinks.

## 0.1.0 — 2026-09-30

Initial implementation with a Python API, command-line interface,
synthetic examples, regression tests, and a GitHub Actions test workflow.
This is an early release; community adoption has not been measured.
