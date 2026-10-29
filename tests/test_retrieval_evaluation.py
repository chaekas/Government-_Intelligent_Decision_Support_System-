from __future__ import annotations

import json
from pathlib import Path

from app.services.evidence_retrieval import search_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_retrieval_cases_return_relevant_document_at_rank_one(tmp_path: Path) -> None:
    cases = json.loads((ROOT / "evaluation" / "retrieval_cases.json").read_text(encoding="utf-8"))
    for case in cases:
        processed = tmp_path / case["case_id"]
        processed.mkdir()
        record = {
            "document_id": case["case_id"],
            "filename": case["relevant_filename"],
            "chunks": [{"page_number": 1, "chunk_index": 0, "text": case["document_text"]}],
        }
        (processed / "record.json").write_text(json.dumps(record), encoding="utf-8")
        result = search_evidence(case["query"], top_k=3, processed_dir=processed)
        assert result["results"], f"No result for evaluation case {case['case_id']}"
        assert result["results"][0]["filename"] == case["relevant_filename"]
        assert result["results"][0]["page_number"] == 1


def test_synthetic_retrieval_scores_are_bounded_and_provenance_is_present(tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    processed.mkdir()
    record = {
        "document_id": "synthetic-1",
        "filename": "road_report.txt",
        "chunks": [{"page_number": 1, "chunk_index": 0, "text": "potholes repair cost"}],
    }
    (processed / "record.json").write_text(json.dumps(record), encoding="utf-8")
    result = search_evidence("potholes repair cost", processed_dir=processed)
    assert 0.0 <= result["results"][0]["score"] <= 1.0
    assert result["results"][0]["document_id"] == "synthetic-1"
    assert result["results"][0]["page_number"] == 1
