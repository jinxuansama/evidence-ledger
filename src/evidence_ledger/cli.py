import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from .core import audit, markdown_report, sha256


def _write_text_atomic(path: Path, text: str) -> None:
    """Replace a report only after a complete same-directory write."""
    try:
        target = path.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ValueError("output path cannot be resolved safely") from exc
    try:
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        mode = None
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            fd = -1
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if fd != -1:
            os.close(fd)
        temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline claim/source provenance checks")
    commands = parser.add_subparsers(dest="command", required=True)
    hash_cmd = commands.add_parser("hash", help="print the SHA-256 of a source snapshot")
    hash_cmd.add_argument("file", type=Path)
    check = commands.add_parser("audit", help="audit a manifest and optional draft")
    check.add_argument("manifest", type=Path)
    check.add_argument("--draft", type=Path)
    check.add_argument("--format", choices=("json", "markdown"), default="json")
    check.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "hash":
            print(sha256(args.file))
            return 0
        report = audit(args.manifest, args.draft, output_path=args.output)
        text = markdown_report(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            _write_text_atomic(args.output, text)
        else:
            print(text, end="")
        return 0 if report["ok"] else 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"evidence-ledger: {exc}", file=sys.stderr)
        return 2
