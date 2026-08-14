from knowledge_intelligence.application.container import build_ingestion_service
from knowledge_intelligence.config import get_settings
from knowledge_intelligence.retrieval.keyword_index import KeywordIndex
from knowledge_intelligence.retrieval.search_service import (
    KnowledgeSearchService,
)
from knowledge_intelligence.retrieval.tokenizer import SearchTokenizer


def main() -> None:
    settings = get_settings()

    ingestion = build_ingestion_service(settings)

    chunks = ingestion.ingest_prefix(settings.s3_prefix)

    index = KeywordIndex(tokenizer=SearchTokenizer())
    index.build(chunks)

    search = KnowledgeSearchService(index)

    print(f"Indexed {len(chunks)} chunks")

    while True:
        query = input("\nQuestion, or 'exit': ").strip()

        if query.lower() == "exit":
            break

        results = search.search(query, limit=5)

        if not results:
            print("No matching document sections found.")
            continue

        for position, result in enumerate(results, start=1):
            print()
            print(f"{position}. {result.chunk.citation.display()}")
            print(f"   Score: {result.score:.6f}")
            print(f"   Matched terms: {', '.join(result.matched_terms)}")
            print()
            print(result.chunk.text[:1_000])


if __name__ == "__main__":
    main()
