"""
Measure section-level retrieval quality on a labelled query set.

Metrics (computed over unique BNS sections, not chunks):
  - hit@1, hit@k : share of queries with an expected section in the top 1 / top k
  - MRR          : mean reciprocal rank of the first expected section

Usage (from backend/):
  python scripts/eval_retrieval.py                     # full hybrid retriever (needs model + vector store)
  python scripts/eval_retrieval.py --lexical-only      # BM25 only, built straight from the CSV (no model needed)
  python scripts/eval_retrieval.py --data data/retrieval_eval_en.json -k 5 --show-misses
"""
import argparse
import json
import os
import sys
import types

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
sys.path.insert(0, BACKEND_DIR)


def _stub_heavy_modules():
    """Let --lexical-only run without chromadb / sentence-transformers installed."""
    for name in ("chromadb", "sentence_transformers", "sentence_transformers.models"):
        try:
            __import__(name)
        except ImportError:
            module = types.ModuleType(name)
            module.PersistentClient = object
            module.SentenceTransformer = object
            module.Transformer = module.Pooling = module.Normalize = object
            sys.modules[name] = module


def _load_samples(path):
    with open(path, "r", encoding="utf-8") as file:
        samples = json.load(file)
    for sample in samples:
        expected = sample.get("expected_sections") or [sample.get("expected_section")]
        sample["expected_sections"] = [str(section) for section in expected if section]
    return samples


def _ranked_sections(results):
    sections = []
    for item in results:
        section = str((item.get("metadata") or {}).get("section_number", ""))
        if section and section not in sections:
            sections.append(section)
    return sections


def _build_lexical_retriever():
    _stub_heavy_modules()
    from app.core.config import settings
    from app.services.ingestion import build_chunks, load_legal_sections
    from app.services.retrieval import MultilingualLegalRetriever, _BM25Index

    class _NoVectorEmbeddings:
        def embed_query(self, query):
            return []

    records = build_chunks(load_legal_sections(settings.BNS_DATA_PATH))
    retriever = MultilingualLegalRetriever.__new__(MultilingualLegalRetriever)
    retriever.embedding_service = _NoVectorEmbeddings()
    retriever.collection = None
    retriever._search_records = records
    retriever._bm25_index = _BM25Index(records)
    return retriever


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", default=os.path.join(BACKEND_DIR, "data", "retrieval_eval_en.json"))
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--lexical-only", action="store_true")
    parser.add_argument("--show-misses", action="store_true")
    args = parser.parse_args()

    if args.lexical_only:
        retriever = _build_lexical_retriever()
    else:
        from app.services.retrieval import MultilingualLegalRetriever

        retriever = MultilingualLegalRetriever()

    from app.services.retrieval import is_english

    samples = [sample for sample in _load_samples(args.data) if is_english(sample["query"])]
    hits_at_1 = hits_at_k = 0
    reciprocal_rank_total = 0.0
    misses = []

    for sample in samples:
        ranked = _ranked_sections(retriever.retrieve(sample["query"], k=args.k)["results"])[: args.k]
        expected = set(sample["expected_sections"])
        rank = next((position for position, section in enumerate(ranked, start=1) if section in expected), None)
        if rank is not None:
            hits_at_k += 1
            hits_at_1 += 1 if rank == 1 else 0
            reciprocal_rank_total += 1.0 / rank
        else:
            misses.append((sample["query"], sorted(expected), ranked))

    total = len(samples) or 1
    mode = "lexical-only" if args.lexical_only else "hybrid"
    print(f"[{mode}] queries={len(samples)}  hit@1={hits_at_1 / total:.3f}  "
          f"hit@{args.k}={hits_at_k / total:.3f}  MRR={reciprocal_rank_total / total:.3f}")

    if args.show_misses:
        for query, expected, ranked in misses:
            print(f"  MISS {query!r}  expected={expected}  got={ranked}")


if __name__ == "__main__":
    main()
