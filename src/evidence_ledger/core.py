"""Deterministic, offline checks of a claim/source ledger."""
from __future__ import annotations

import errno
import hashlib
import json
import re
from pathlib import Path

MARKER = re.compile(r"\[\[claim:([A-Za-z0-9_.-]+)\]\]")
ID = re.compile(r"[A-Za-z0-9_.-]+\Z")


def sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _index(items: object, label: str) -> dict:
    if not isinstance(items, list):
        raise ValueError(f"{label} must be a list")
    result = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"{label} entries must be objects")
        key = item.get("id")
        if not isinstance(key, str) or not ID.fullmatch(key):
            raise ValueError(f"invalid {label} id: {key!r}")
        if key in result:
            raise ValueError(f"duplicate {label} id: {key}")
        result[key] = item
    return result


def audit(manifest_path: str | Path, draft_path: str | Path | None = None) -> dict:
    """Check hashes, exact excerpts, and explicit draft references.

    A passing check establishes provenance consistency, not source truth or
    semantic entailment. Local source paths must stay within the manifest tree.
    """
    manifest_path = Path(manifest_path).resolve()
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("version") != 1:
        raise ValueError("manifest must be an object with version=1")
    sources = _index(doc.get("sources"), "sources")
    claims = _index(doc.get("claims"), "claims")
    issues, texts, valid_sources = [], {}, set()

    def issue(code, item, message, severity="error"):
        issues.append(dict(code=code, item=item, message=message, severity=severity))

    for key, source in sources.items():
        raw = source.get("path")
        if not isinstance(raw, str) or not raw or "\x00" in raw or Path(raw).is_absolute():
            issue("unsafe_path", key, "source path must be relative")
            continue
        try:
            path = (manifest_path.parent / raw).resolve()
        except (OSError, RuntimeError, ValueError):
            issue("unsafe_path", key, "source path cannot be resolved safely")
            continue
        if not path.is_relative_to(manifest_path.parent):
            issue("unsafe_path", key, "source path escapes the manifest directory")
            continue
        expected = source.get("sha256")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            issue("missing_hash", key, "a lowercase SHA-256 digest is required")
            continue
        try:
            blob = path.read_bytes()
            text = blob.decode("utf-8")
        except (OSError, UnicodeError) as exc:
            if isinstance(exc, OSError) and exc.errno == errno.ELOOP:
                # Non-strict resolve() can leave loops unresolved on Python 3.13+.
                issue("unsafe_path", key, "source path contains a symlink loop")
            else:
                issue("unreadable_source", key, "source must be a readable UTF-8 text file")
            continue
        if hashlib.sha256(blob).hexdigest() != expected:
            issue("hash_mismatch", key, "snapshot differs from the recorded digest")
            continue
        texts[key] = text
        valid_sources.add(key)

    checked = []
    for key, claim in claims.items():
        before = len(issues)
        if not isinstance(claim.get("text"), str) or not claim["text"].strip():
            issue("missing_claim_text", key, "claim text must be non-empty")
        kind = claim.get("kind")
        if kind not in ("fact", "interpretation"):
            issue("invalid_kind", key, "kind must be fact or interpretation")
        source_id = claim.get("source_id")
        if not isinstance(source_id, str) or source_id not in sources:
            issue("unknown_source", key, "source_id does not identify a source")
        elif source_id not in valid_sources:
            issue("invalid_source", key, "source snapshot did not pass its checks")
        else:
            quote = claim.get("quote")
            if not isinstance(quote, str) or not quote.strip():
                issue("missing_quote", key, "a non-empty exact supporting excerpt is required")
            elif quote not in texts[source_id]:
                issue("quote_not_found", key, "excerpt is not present verbatim in the snapshot")
        if kind == "interpretation" and not isinstance(claim.get("rationale"), str):
            issue("missing_rationale", key, "interpretation needs a written rationale")
        elif kind == "interpretation" and not claim["rationale"].strip():
            issue("missing_rationale", key, "interpretation rationale cannot be empty")
        checked.append(dict(id=key, kind=kind, provenance_ok=len(issues) == before))

    used = []
    if draft_path is not None:
        draft = Path(draft_path).read_text(encoding="utf-8")
        used = sorted(set(MARKER.findall(draft)))
        for key in used:
            if key not in claims:
                issue("unknown_claim", key, "draft references an unknown claim")
        residue = MARKER.sub("", draft)
        if "[[claim:" in residue:
            issue("malformed_marker", "draft", "an incomplete or invalid claim marker remains")
        if not used:
            issue("no_markers", "draft", "no explicit claim references were found", "warning")
        for key in sorted(set(claims) - set(used)):
            issue("unused_claim", key, "ledger claim is not referenced in the draft", "warning")

    return dict(version=1, ok=not any(i["severity"] == "error" for i in issues),
                source_count=len(sources), claim_count=len(claims), claims=checked,
                referenced_claims=used, issues=issues,
                limitation="Provenance checks do not verify truth, relevance, or entailment.")


def markdown_report(report: dict) -> str:
    def escape(text):
        return str(text).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    lines = ["# Evidence ledger audit", "", f"Provenance checks: {'PASS' if report['ok'] else 'FAIL'}",
             "", report["limitation"], "", "| Severity | Code | Item | Detail |",
             "| --- | --- | --- | --- |"]
    for issue in report["issues"]:
        lines.append("| " + " | ".join(escape(issue[k]) for k in ("severity", "code", "item", "message")) + " |")
    if not report["issues"]:
        lines.append("| — | — | — | No provenance inconsistencies found |")
    return "\n".join(lines) + "\n"
