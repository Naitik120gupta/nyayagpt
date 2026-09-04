"""
Diagnose why specific queries miss expected BNS sections.

For each failing query, this prints:
  - the BM25 tokens the query is broken into (reveals stemming/exact-match issues)
  - whether the expected sections show up in the raw vector candidate pool at all
  - their raw vector similarity, BM25 score, combined hybrid score, and rank
  - what the top-5 returned actually are
  - whether the MIN_RELEVANCE_SCORE threshold is filtering the expected sections out

Run from backend/:  python scripts/diagnose_retrieval.py
"""
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.insert(0, BACKEND_DIR)

from app.core.config import settings
from app.services.retrieval import (
    MultilingualLegalRetriever,
    _tokenize_text,
    _normalize_query,
    _combine_modalities,
)

CASES = [
    ("A man grabbed and molested me on a crowded bus",     {"74", "75"}),
    ("Someone broke into my house at night",               {"329"}),
    ("A person is stalking me and sending lewd messages",  {"79", "75"}),
    # Include one that PASSES to compare against
    ("Sexual assault and rape committed against a woman",  {"63"}),
]


def _section_of(candidate):
    return (candidate.get("metadata") or {}).get("section_number", "")


def diagnose(retriever: MultilingualLegalRetriever, query: str, expected: set[str]):
    print("=" * 100)
    print(f"QUERY: {query!r}")
    print(f"EXPECTED SECTIONS: {sorted(expected)}")
    print(f"BM25 TOKENS: {_tokenize_text(query)}")

    normalized = _normalize_query(query)
    query_embedding = retriever.embedding_service.embed_query(normalized)

    # Pull a MUCH bigger vector pool than production uses, so we can see
    # where the expected sections rank even if they're way down.
    raw = retriever.collection.query(
        query_embeddings=[query_embedding],
        n_results=100,
        include=["documents", "metadatas", "distances"],
    )
    docs = raw["documents"][0]
    metas = raw["metadatas"][0]
    dists = raw["distances"][0]
    ids = raw["ids"][0]

    print(f"\n-- Vector-only ranking (top 100 from Chroma) --")
    print(f"{'rank':>4}  {'sec':>4}  {'sim':>6}  {'dist':>6}  id")
    expected_ranks = {}
    for rank, (doc, meta, dist, cid) in enumerate(zip(docs, metas, dists, ids), start=1):
        sec = (meta or {}).get("section_number", "")
        similarity = 1.0 - dist if dist is not None else 1.0
        if sec in expected:
            expected_ranks.setdefault(sec, (rank, similarity, cid))
            print(f"{rank:>4}  {sec:>4}  {similarity:>6.3f}  {dist:>6.3f}  {cid}   <-- EXPECTED")
        elif rank <= 10:
            print(f"{rank:>4}  {sec:>4}  {similarity:>6.3f}  {dist:>6.3f}  {cid}")

    for sec in sorted(expected):
        if sec not in expected_ranks:
            print(f"  !! Section {sec} NOT in top 100 vector candidates at all")

    # Now the full production retrieval — hybrid + threshold
    print(f"\n-- Production retrieve() output (k=5, MIN_RELEVANCE_SCORE={settings.MIN_RELEVANCE_SCORE}) --")
    payload = retriever.retrieve(query, k=5)
    for rank, item in enumerate(payload["results"], start=1):
        sec = _section_of(item)
        marker = "  <-- EXPECTED" if sec in expected else ""
        print(f"  {rank}. sec {sec:>4}  hybrid={item.get('score', 0.0):.3f}  "
              f"vec={item.get('vector_score', 0.0):.3f}  bm25={item.get('bm25_score', 0.0):.3f}"
              f"{marker}")

    # Also inspect the pre-threshold merged pool to see where expected sections
    # rank hybrid-wise, and whether the threshold killed them
    print(f"\n-- Pre-threshold hybrid ranking (top 15) --")
    v_cands = retriever._collect_vector_candidates(query_embedding, 5)
    b_cands = retriever._collect_bm25_candidates(normalized)
    merged = retriever._merge_candidates(v_cands, b_cands)
    for rank, item in enumerate(merged[:15], start=1):
        sec = _section_of(item)
        keep = "keep" if item.get("score", 0.0) >= settings.MIN_RELEVANCE_SCORE else "DROP"
        marker = "  <-- EXPECTED" if sec in expected else ""
        print(f"  {rank}. sec {sec:>4}  hybrid={item.get('score', 0.0):.3f}  "
              f"vec={item.get('vector_score', 0.0):.3f}  bm25={item.get('bm25_score', 0.0):.3f}  "
              f"[{keep}]{marker}")

    # Show BM25 hits for the query — any doc with any query token?
    print(f"\n-- BM25 hits (documents containing ANY query token) --")
    b_hits = [(item, item.get("bm25_score", 0.0)) for item in b_cands]
    b_hits.sort(key=lambda x: x[1], reverse=True)
    if not b_hits:
        print("  (none — no document contains any of the query tokens exactly)")
    for item, score in b_hits[:10]:
        sec = _section_of(item)
        marker = "  <-- EXPECTED" if sec in expected else ""
        print(f"  sec {sec:>4}  bm25_norm={score:.3f}{marker}")
    print()


def main():
    print(f"Loading retriever (MIN_RELEVANCE_SCORE={settings.MIN_RELEVANCE_SCORE}, "
          f"model={settings.LOCAL_EMBEDDING_MODEL}) ...")
    retriever = MultilingualLegalRetriever()
    print(f"BM25 corpus size: {len(retriever._search_records)} documents\n")

    for query, expected in CASES:
        diagnose(retriever, query, expected)


if __name__ == "__main__":
    main()