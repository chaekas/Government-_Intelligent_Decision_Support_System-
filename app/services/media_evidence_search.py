"""Deterministic lexical search over locally saved timestamped transcript segments."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from app.services.transcription import TRANSCRIPT_DIR

TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    return [token.casefold() for token in TOKEN_RE.findall(value) if token.strip()]


def _load_segments(transcript_dir: Path) -> list[dict[str, Any]]:
    """Load valid transcript segments while skipping corrupt or incomplete files."""
    rows: list[dict[str, Any]] = []
    if not transcript_dir.is_dir():
        return rows
    for path in sorted(transcript_dir.glob("*.json")):
        try:
            transcript = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(transcript, dict) or not isinstance(transcript.get("segments"), list):
            continue
        media_id = transcript.get("media_id")
        filename = transcript.get("filename")
        if not isinstance(media_id, str) or not isinstance(filename, str):
            continue
        for index, segment in enumerate(transcript["segments"]):
            if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
                continue
            text = segment["text"].strip()
            try:
                start = float(segment["start_seconds"])
                end = float(segment["end_seconds"])
            except (KeyError, TypeError, ValueError):
                continue
            if not text or not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
                continue
            rows.append({
                "media_id": media_id,
                "filename": filename,
                "segment_index": index,
                "start_seconds": start,
                "end_seconds": end,
                "text": text,
            })
    return rows


def search_media_evidence(
    query: str, top_k: int = 5, transcript_dir: Path | None = None
) -> dict[str, Any]:
    """Return matching transcript segments and their source media timestamps.

    Scores are transparent heuristic rankings, not confidence probabilities.
    Only persisted transcript segments are searched; original media is not changed.
    """
    query_tokens = list(dict.fromkeys(_tokens(query)))
    if not query_tokens:
        return {"query": query, "total_matches": 0, "results": []}

    scored: list[dict[str, Any]] = []
    normalized_query = " ".join(query_tokens)
    for segment in _load_segments(transcript_dir or TRANSCRIPT_DIR):
        text_tokens = _tokens(segment["text"])
        counts: dict[str, int] = {}
        for token in text_tokens:
            counts[token] = counts.get(token, 0) + 1
        matched = [token for token in query_tokens if token in counts]
        if not matched:
            continue
        coverage = len(matched) / len(query_tokens)
        frequency = sum(min(counts[token], 3) for token in matched)
        frequency_bonus = min(0.15, math.log1p(frequency) / 20)
        phrase_bonus = 0.15 if normalized_query in " ".join(text_tokens) else 0.0
        scored.append({
            **segment,
            "score": round(min(1.0, coverage * 0.8 + frequency_bonus + phrase_bonus), 4),
            "matched_terms": matched,
        })
    scored.sort(key=lambda item: (
        -item["score"], item["filename"].casefold(), item["start_seconds"],
        item["end_seconds"], item["segment_index"],
    ))
    return {"query": query, "total_matches": len(scored), "results": scored[:top_k]}
