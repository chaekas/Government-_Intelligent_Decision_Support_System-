"""Deterministic comparison and source-linked report drafting workflows.

These workflows organize retrieved passages. They do not infer truth, establish
that two sources agree, or generate claims unsupported by the supplied evidence.
"""
from __future__ import annotations

from typing import Any

from app.services.evidence_retrieval import search_evidence
from app.services.media_evidence_search import search_media_evidence


LIMITATIONS = [
    "Search scores are heuristic ranking signals, not probabilities or calibrated confidence.",
    "A missing search result does not prove that the topic is absent from the source records.",
    "The workflow does not automatically determine whether sources agree or conflict; a reviewer must compare the cited passages.",
    "Document extraction and machine-generated transcripts may contain errors. Verify each passage against the original source.",
    "This draft is not a finding, recommendation, or final government decision.",
]


def compare_evidence(
    query: str,
    top_k: int = 5,
    document_query: str | None = None,
    media_query: str | None = None,
) -> dict[str, Any]:
    """Search document and transcript evidence independently and preserve provenance."""
    doc_query = (document_query or query).strip()
    aud_query = (media_query or query).strip()
    docs = search_evidence(doc_query, top_k)
    media = search_media_evidence(aud_query, top_k)

    document_results = [
        {
            "modality": "document",
            "source_id": str(item["document_id"]),
            "filename": str(item["filename"]),
            "location": f"page {item['page_number']}, chunk {item['chunk_index']}",
            "text": str(item["text"]),
            "score": float(item["score"]),
            "matched_terms": list(item["matched_terms"]),
        }
        for item in docs["results"]
    ]
    media_results = [
        {
            "modality": "audio_video",
            "source_id": str(item["media_id"]),
            "filename": str(item["filename"]),
            "location": (
                f"segment {item['segment_index']}, "
                f"{float(item['start_seconds']):.2f}s–{float(item['end_seconds']):.2f}s"
            ),
            "text": str(item["text"]),
            "score": float(item["score"]),
            "matched_terms": list(item["matched_terms"]),
        }
        for item in media["results"]
    ]

    if document_results and media_results:
        coverage = "both_modalities"
        assessment = "UNCERTAIN"
        note = (
            "Matching evidence was found in documents and transcripts. This indicates coverage "
            "across both modalities, not agreement between sources. Compare the cited passages "
            "and original files before deciding whether they match or conflict."
        )
    elif document_results:
        coverage = "documents_only"
        assessment = "SINGLE_MODALITY"
        note = "Evidence was found in documents only. Audio/video evidence was not retrieved for this query."
    elif media_results:
        coverage = "media_only"
        assessment = "SINGLE_MODALITY"
        note = "Evidence was found in saved audio/video transcripts only. Document evidence was not retrieved."
    else:
        coverage = "no_evidence"
        assessment = "UNCERTAIN"
        note = (
            "No matching evidence was retrieved from the indexed documents or saved transcripts. "
            "This does not prove that the topic is absent from the records."
        )

    return {
        "query": query,
        "document_query": doc_query,
        "media_query": aud_query,
        "coverage": coverage,
        "assessment": assessment,
        "assessment_note": note,
        "document_results": document_results,
        "media_results": media_results,
        "evidence_count": len(document_results) + len(media_results),
        "review_required": True,
    }


def draft_report(
    title: str,
    question: str,
    top_k: int = 5,
    document_query: str | None = None,
    media_query: str | None = None,
) -> dict[str, Any]:
    """Create a review-ready Markdown draft whose evidence section quotes sources."""
    comparison = compare_evidence(
        query=question,
        top_k=top_k,
        document_query=document_query,
        media_query=media_query,
    )
    evidence = comparison["document_results"] + comparison["media_results"]
    lines = [
        f"# {title.strip()}",
        "",
        f"**Question / topic:** {question.strip()}",
        "",
        f"**Evidence coverage:** {comparison['coverage'].replace('_', ' ').title()}",
        f"**Assessment:** {comparison['assessment']}",
        "",
        "## Preliminary overview",
        comparison["assessment_note"],
        "",
        "## Retrieved evidence",
    ]
    if evidence:
        for index, item in enumerate(evidence, start=1):
            citation = (
                f"[E{index}] {item['filename']} — {item['location']} "
                f"(source ID: {item['source_id']}; modality: {item['modality']}; "
                f"lexical score: {item['score']:.3f})"
            )
            lines.extend(["", f"### {citation}", "", f"> {item['text'].replace(chr(10), chr(10) + '> ')}", ""])
    else:
        lines.extend(["", "No matching passages were retrieved. Do not treat this as proof that no evidence exists.", ""])

    lines.extend(["", "## Reviewer actions", ""])
    lines.extend([
        "- Open each cited source and verify the quoted passage and its context.",
        "- Compare dates, quantities, names, and other material details across sources.",
        "- Record any agreement, partial support, conflict, or unresolved uncertainty with a reason.",
        "- Add conclusions or recommendations only when supported by reviewed evidence.",
        "",
        "## Limitations",
    ])
    lines.extend([f"- {limitation}" for limitation in LIMITATIONS])
    lines.extend(["", "_Draft generated from retrieved passages. Human review is required before use._"])

    return {
        "title": title.strip(),
        "question": question.strip(),
        "assessment": comparison["assessment"],
        "evidence_count": len(evidence),
        "evidence": evidence,
        "draft_markdown": "\n".join(lines),
        "limitations": LIMITATIONS,
        "human_review_required": True,
    }
