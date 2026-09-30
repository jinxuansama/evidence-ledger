import argparse
import json
import sys
from pathlib import Path

from .core import audit, markdown_report, sha256


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
        report = audit(args.manifest, args.draft)
        text = markdown_report(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0 if report["ok"] else 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"evidence-ledger: {exc}", file=sys.stderr)
        return 2
