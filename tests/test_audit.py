import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from evidence_ledger.core import audit
from evidence_ledger.cli import main


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.txt"
        self.source.write_text("Synthetic firm A earned 12 units.\n", encoding="utf-8")
        self.manifest = self.root / "ledger.json"
        self.doc = dict(version=1, sources=[dict(id="s1", path="source.txt", sha256=hashlib.sha256(self.source.read_bytes()).hexdigest())],
                        claims=[dict(id="c1", text="Firm A earned 12 units.", kind="fact", source_id="s1", quote="earned 12 units")])

    def run_audit(self, draft=None):
        self.manifest.write_text(json.dumps(self.doc), encoding="utf-8")
        return audit(self.manifest, draft)

    def test_consistent_provenance(self):
        self.assertTrue(self.run_audit()["ok"])

    def test_tampering_fails_even_when_quote_remains(self):
        self.source.write_text("Synthetic firm A earned 12 units. Altered.\n")
        self.assertIn("hash_mismatch", [i["code"] for i in self.run_audit()["issues"]])

    def test_unmatched_quote(self):
        self.doc["claims"][0]["quote"] = "earned 120 units"
        self.assertFalse(self.run_audit()["ok"])

    def test_unknown_and_malformed_references(self):
        draft = self.root / "draft.md"
        draft.write_text("Claim [[claim:missing]] and [[claim:bad id]]")
        codes = {i["code"] for i in self.run_audit(draft)["issues"]}
        self.assertTrue({"unknown_claim", "malformed_marker"} <= codes)

    def test_traversal_rejected(self):
        self.doc["sources"][0]["path"] = "../private.txt"
        self.assertIn("unsafe_path", {i["code"] for i in self.run_audit()["issues"]})

    def test_symlink_escape_rejected(self):
        outside = self.root.parent / (self.root.name + "-outside.txt")
        outside.write_text("earned 12 units")
        self.addCleanup(outside.unlink)
        link = self.root / "link.txt"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.doc["sources"][0]["path"] = "link.txt"
        self.assertIn("unsafe_path", {i["code"] for i in self.run_audit()["issues"]})

    def test_duplicate_ids_raise(self):
        self.doc["claims"].append(self.doc["claims"][0].copy())
        with self.assertRaises(ValueError):
            self.run_audit()

    def test_interpretation_requires_rationale(self):
        self.doc["claims"][0]["kind"] = "interpretation"
        self.assertFalse(self.run_audit()["ok"])
        self.doc["claims"][0]["rationale"] = "Hypothesis only; this excerpt does not establish a causal mechanism."
        self.assertTrue(self.run_audit()["ok"])

    def test_valid_excerpt_does_not_establish_truth(self):
        self.doc["claims"][0]["text"] = "The moon is made of cheese."
        report = self.run_audit()
        self.assertTrue(report["ok"])
        self.assertIn("do not verify truth", report["limitation"])

    def test_cli_error_has_no_traceback(self):
        self.manifest.write_text("{bad")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["audit", str(self.manifest)]), 2)
        self.assertNotIn("Traceback", err.getvalue())

    def test_empty_quote_and_invalid_source_types(self):
        self.doc["claims"][0]["quote"] = " "
        self.doc["claims"][0]["source_id"] = []
        self.assertFalse(self.run_audit()["ok"])


if __name__ == "__main__":
    unittest.main()
