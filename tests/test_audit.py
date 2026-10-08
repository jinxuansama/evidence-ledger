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

    def test_duplicate_json_members_raise_before_auditing(self):
        original = json.dumps(self.doc)
        cases = {
            "sources": original[:-1] + ', "sources": []}',
            "id": original.replace('"id": "s1"', '"id": "hidden", "id": "s1"', 1),
            "source_id": original.replace('"source_id": "s1"',
                                           '"source_id": "missing", "source_id": "s1"'),
            "reviewed": original[:-1] + ', "metadata": {"reviewed": false, "reviewed": true}}',
        }
        for key, manifest in cases.items():
            with self.subTest(key=key):
                self.manifest.write_text(manifest, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, f"duplicate JSON member: {key!r}"):
                    audit(self.manifest)

    def test_escaped_duplicate_key_is_a_cli_input_error_without_report(self):
        manifest = json.dumps(self.doc).replace(
            '"id": "s1"', '"id": "hidden", "\\u0069d": "s1"', 1)
        self.manifest.write_text(manifest, encoding="utf-8")
        output = self.root / "report.json"
        output.write_text("previous report", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["audit", str(self.manifest), "--output", str(output)]), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("duplicate JSON member: 'id'", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertEqual(output.read_text(encoding="utf-8"), "previous report")

    def test_member_names_can_repeat_in_separate_objects(self):
        self.doc["sources"].append(dict(self.doc["sources"][0], id="s2"))
        self.doc["claims"].append(dict(self.doc["claims"][0], id="c2", source_id="s2"))
        self.doc["metadata"] = {"left": {"reviewed": True}, "right": {"reviewed": False}}
        report = self.run_audit()
        self.assertTrue(report["ok"])
        self.assertEqual((report["source_count"], report["claim_count"]), (2, 2))

    def test_symlink_loop_is_reported_without_aborting_other_claims(self):
        loop = self.root / "loop.txt"
        try:
            loop.symlink_to(loop.name)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.doc["sources"].insert(0, dict(id="loop", path=loop.name, sha256="0" * 64))
        self.doc["claims"].append(dict(id="bad", text="Bad source", kind="fact",
                                       source_id="loop", quote="anything"))
        report = self.run_audit()
        self.assertFalse(report["ok"])
        self.assertIn(("unsafe_path", "loop"), {(i["code"], i["item"]) for i in report["issues"]})
        checked = {claim["id"]: claim["provenance_ok"] for claim in report["claims"]}
        self.assertTrue(checked["c1"])
        self.assertFalse(checked["bad"])
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(main(["audit", str(self.manifest)]), 1)
        self.assertFalse(json.loads(out.getvalue())["ok"])
        self.assertEqual(err.getvalue(), "")

    def test_embedded_null_path_is_a_structured_audit_error(self):
        self.doc["sources"][0]["path"] = "source\x00.txt"
        report = self.run_audit()
        self.assertFalse(report["ok"])
        self.assertIn("unsafe_path", {i["code"] for i in report["issues"]})

    def test_in_directory_symlink_still_passes(self):
        link = self.root / "link.txt"
        try:
            link.symlink_to(self.source.name)
        except OSError:
            self.skipTest("symlinks unavailable")
        self.doc["sources"][0]["path"] = link.name
        self.assertTrue(self.run_audit()["ok"])

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
