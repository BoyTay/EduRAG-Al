import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "experiments" / "evaluation"))

from scoring import load_cases, score_case, summarize  # noqa: E402


def make_case(**overrides):
    case = {
        "id": "c1",
        "category": "simple_table",
        "question": "IELTS bao nhiêu thì đạt bậc 4?",
        "expected_values": [],
        "forbidden": [],
        "source_filename": "A.pdf",
        "pages": [2],
        "should_refuse": False,
    }
    case.update(overrides)
    return case


class ScoreCaseTests(unittest.TestCase):
    def test_value_ok_requires_every_group_and_ignores_accents(self):
        case = make_case(expected_values=[["5.5-6.5", "5,5-6,5"], ["IELTS"]])
        record = score_case(case, "IELTS 5,5-6,5 tương đương bậc 4", [], None, 1.0)
        self.assertTrue(record["value_ok"])
        self.assertEqual(record["missing_values"], [])

        accented = make_case(expected_values=[["mức lương cơ sở"]])
        self.assertTrue(score_case(accented, "60% MUC LUONG CO SO", [], None, 1.0)["value_ok"])

    def test_forbidden_value_fails_case(self):
        case = make_case(expected_values=[["5.5-6.5"]], forbidden=[["4.0-5.0"]])
        record = score_case(case, "Bậc 4 là 5.5-6.5, bậc 3 là 4.0-5.0", [], None, 1.0)
        self.assertFalse(record["value_ok"])
        self.assertEqual(record["forbidden_found"], [["4.0-5.0"]])

    def test_source_ok_needs_same_file_and_page(self):
        sources = [{"filename": "A.pdf", "page": 2}]
        self.assertTrue(score_case(make_case(pages=[2]), "x", sources, None, 1.0)["source_ok"])
        self.assertFalse(score_case(make_case(pages=[3]), "x", sources, None, 1.0)["source_ok"])
        other_file = make_case(source_filename="B.pdf", pages=[2])
        self.assertFalse(score_case(other_file, "x", sources, None, 1.0)["source_ok"])

    def test_refusal_case_scores_on_refusal_only(self):
        case = make_case(should_refuse=True, expected_values=[["không thể khớp"]])
        record = score_case(case, "Xin lỗi, tôi không tìm thấy", [], "low_score=0.1", 2.0)
        self.assertTrue(record["refusal_detected"])
        self.assertTrue(record["refusal_ok"])
        self.assertTrue(record["value_ok"])
        self.assertTrue(record["source_ok"])

        answered = score_case(case, "Có, học phí là...", [], None, 2.0)
        self.assertFalse(answered["value_ok"])
        self.assertFalse(answered["refusal_ok"])


class SummarizeTests(unittest.TestCase):
    def test_summarize_excludes_errors_and_reports_count(self):
        good = score_case(make_case(expected_values=[["a"]]), "a", [{"filename": "A.pdf", "page": 2}], None, 1.0)
        bad = score_case(make_case(expected_values=[["b"]]), "a", [], None, 3.0)
        records = [good, dict(good), bad, {"case_id": "x", "category": "simple_table", "status": "case_error"}]
        summary = summarize(records)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["value_accuracy"], round(2 / 3, 4))
        self.assertEqual(summary["source_accuracy"], round(2 / 3, 4))
        self.assertEqual(summary["by_category"]["simple_table"], round(2 / 3, 4))

    def test_false_refusal_rate_counts_refusals_on_answerable_cases(self):
        records = [score_case(make_case(), "x", [], None, 1.0) for _ in range(3)]
        records.append(score_case(make_case(), "Xin lỗi", [], "low_score=0.2", 1.0))
        refusal_case = make_case(should_refuse=True)
        records.append(score_case(refusal_case, "Có thông tin", [], None, 1.0))
        summary = summarize(records)
        self.assertEqual(summary["false_refusal_rate"], 0.25)
        self.assertEqual(summary["missed_refusal_rate"], 1.0)

    def test_latency_percentiles(self):
        records = [score_case(make_case(), "x", [], None, float(s)) for s in range(1, 11)]
        summary = summarize(records)
        self.assertGreaterEqual(summary["p95_seconds"], summary["p50_seconds"])
        self.assertAlmostEqual(summary["p50_seconds"], 5.5, places=1)
        single = summarize([score_case(make_case(), "x", [], None, 4.0)])
        self.assertEqual(single["p50_seconds"], 4.0)
        self.assertEqual(single["p95_seconds"], 4.0)


class LoadCasesTests(unittest.TestCase):
    def _write(self, cases):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "cases.json"
        path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        return path

    def test_load_cases_rejects_duplicate_ids_and_missing_keys(self):
        with self.assertRaises(ValueError) as duplicate:
            load_cases(self._write([make_case(), make_case()]))
        self.assertIn("c1", str(duplicate.exception))

        incomplete = make_case(id="c2")
        del incomplete["pages"]
        with self.assertRaises(ValueError) as missing:
            load_cases(self._write([incomplete]))
        self.assertIn("c2", str(missing.exception))

    def test_table_cases_file_is_valid(self):
        cases = load_cases(REPO_ROOT / "experiments" / "evaluation" / "table_cases.json")
        self.assertEqual(len(cases), 28)
        counts = {}
        for case in cases:
            counts[case["category"]] = counts.get(case["category"], 0) + 1
        self.assertEqual(counts, {
            "simple_table": 8, "wrapped_rows": 3, "page_continuation": 3,
            "prose_layout": 3, "labels": 3, "ocr_scan": 4, "refusal": 4,
        })
        for case in cases:
            if case["should_refuse"]:
                self.assertEqual(case["expected_values"], [], case["id"])
            else:
                self.assertTrue(case["expected_values"] and case["pages"], case["id"])

    def test_load_cases_returns_valid_cases(self):
        cases = load_cases(self._write([make_case(), make_case(id="c2")]))
        self.assertEqual([case["id"] for case in cases], ["c1", "c2"])


if __name__ == "__main__":
    unittest.main()
