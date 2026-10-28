"""Local, deterministic keyword retrieval over persisted document chunks.

This module deliberately uses no remote model or external API. Search results
carry document and page provenance and include only chunks that match the query.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from app.services.document_ingestion import PROCESSED_DIR

TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)


def _tokens(value: str) -> list[str]:
    """Return normalized alphanumeric tokens, retaining meaningful short terms."""
    return [token.casefold() for token in TOKEN_RE.findall(value) if token.strip()]


def _load_chunks(processed_dir: Path) -> list[dict[str, Any]]:
    """Load valid document chunks while skipping corrupt or incomplete records."""
    chunks: list[dict[str, Any]] = []
    if not processed_dir.is_dir():
        return chunks
    for path in sorted(processed_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict) or not isinstance(record.get("chunks"), list):
            continue
        for chunk in record["chunks"]:
            if not isinstance(chunk, dict) or not isinstance(chunk.get("text"), str):
                continue
            text = chunk["text"].strip()
            if not text:
                continue
            try:
                page_number = int(chunk["page_number"])
                chunk_index = int(chunk["chunk_index"])
            except (KeyError, TypeError, ValueError):
                continue
            if page_number < 1 or chunk_index < 0:
                continue
            chunks.append({
                "document_id": str(record.get("document_id", path.stem)),
                "filename": str(record.get("filename", "unknown")),
                "chunk_index": chunk_index,
                "page_number": page_number,
                "text": text,
            })
    return chunks


def search_evidence(query: str, top_k: int = 5, processed_dir: Path | None = None) -> dict[str, Any]:
    """Rank matching chunks with a deterministic lexical score and provenance.

    The score is a transparent heuristic (query-token coverage plus a small
    phrase bonus), not a probability or a calibrated confidence value.
    """
    query_tokens = list(dict.fromkeys(_tokens(query)))
    if not query_tokens:
        return {"query": query, "total_matches": 0, "results": []}

    chunks = _load_chunks(processed_dir or PROCESSED_DIR)
    scored: list[dict[str, Any]] = []
    query_set = set(query_tokens)
    normalized_query = " ".join(query_tokens)
    for chunk in chunks:
        text_tokens = _tokens(chunk["text"])
        if not text_tokens:
            continue
        token_counts: dict[str, int] = {}
        for token in text_tokens:
            token_counts[token] = token_counts.get(token, 0) + 1
        matched_terms = [token for token in query_tokens if token in token_counts]
        if not matched_terms:
            continue
        coverage = len(matched_terms) / len(query_tokens)
        frequency = sum(min(token_counts[token], 3) for token in matched_terms)
        frequency_bonus = min(0.15, math.log1p(frequency) / 20)
        normalized_text = " ".join(text_tokens)
        phrase_bonus = 0.15 if normalized_query in normalized_text else 0.0
        score = min(1.0, coverage * 0.8 + frequency_bonus + phrase_bonus)
        scored.append({
            "document_id": chunk["document_id"],
            "filename": chunk["filename"],
            "chunk_index": chunk["chunk_index"],
            "page_number": chunk["page_number"],
            "text": chunk["text"],
            "score": round(score, 4),
            "matched_terms": matched_terms,
        })

    scored.sort(key=lambda item: (-item["score"], item["filename"].casefold(), item["page_number"], item["chunk_index"]))
    return {"query": query, "total_matches": len(scored), "results": scored[:top_k]}
