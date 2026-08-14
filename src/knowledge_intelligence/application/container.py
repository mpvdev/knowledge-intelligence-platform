from dataclasses import dataclass

from knowledge_intelligence.agents.github_knowledge import GitHubKnowledgeAgentFactory
from knowledge_intelligence.agents.platform_knowledge import PlatformKnowledgeAgentFactory
from knowledge_intelligence.application.github_knowledge_service import GitHubKnowledgeService
from knowledge_intelligence.application.platform_knowledge_service import (
    PlatformKnowledgeService,
)
from knowledge_intelligence.application.unified_knowledge_service import (
    UnifiedKnowledgeService,
)
from knowledge_intelligence.chunking.chunker import DocumentChunker
from knowledge_intelligence.chunking.text_splitter import TextSplitter
from knowledge_intelligence.config import Settings
from knowledge_intelligence.connectors.github.client import GitHubClientConfig, GitHubCodeClient
from knowledge_intelligence.connectors.local_repository import LocalRepositoryReader
from knowledge_intelligence.connectors.s3.chunk_repository import S3ChunkRepository
from knowledge_intelligence.connectors.s3.client import (
    create_s3_client,
    create_s3vectors_client,
)
from knowledge_intelligence.connectors.s3.repository import S3DocumentRepository
from knowledge_intelligence.connectors.s3vectors_repository import S3VectorsRepository
from knowledge_intelligence.embeddings.provider import (
    OpenAIEmbeddingConfig,
    OpenAIEmbeddingProvider,
)
from knowledge_intelligence.parsers.registry import DocumentParserRegistry
from knowledge_intelligence.registry.loader import ComponentRegistryLoader
from knowledge_intelligence.registry.registry import ComponentRegistry
from knowledge_intelligence.retrieval.github_search import GitHubRepositorySearchAdapter
from knowledge_intelligence.retrieval.hybrid import HybridSearchService, RetrievalMode
from knowledge_intelligence.retrieval.keyword_index import KeywordIndex
from knowledge_intelligence.retrieval.search_service import KnowledgeSearchService
from knowledge_intelligence.retrieval.semantic_search import SemanticSearchService
from knowledge_intelligence.retrieval.tokenizer import SearchTokenizer
from knowledge_intelligence.services.document_classification import DocumentClassificationService
from knowledge_intelligence.services.knowledge_ingestion import KnowledgeIngestionService
from knowledge_intelligence.services.pdf_enrichment import PDFEnrichmentService
from knowledge_intelligence.services.vector_ingestion import VectorIngestionService
from knowledge_intelligence.services.visual_document_processing import (
    VisualDocumentProcessingService,
)
from knowledge_intelligence.tools.knowledge_search import KnowledgeSearchAdapter
from knowledge_intelligence.visual.analyser import VisualPageAnalyser
from knowledge_intelligence.visual.detector import VisualPageDetector, VisualPageDetectorConfig
from knowledge_intelligence.visual.renderer import PDFPageRenderer, PDFPageRendererConfig
from knowledge_intelligence.visual.strands_analyser import (
    StrandsVisualAnalyserConfig,
    StrandsVisualPageAnalyser,
)

CHUNK_MAX_CHARACTERS = 2_000
CHUNK_OVERLAP_CHARACTERS = 250


@dataclass(frozen=True)
class ApplicationContainer:
    platform_knowledge_service: PlatformKnowledgeService
    unified_knowledge_service: UnifiedKnowledgeService
    github_knowledge_service: GitHubKnowledgeService | None
    indexed_chunk_count: int
    vector_retrieval_configured: bool = False
    vector_retrieval_reachable: bool = False


def build_application(settings: Settings) -> ApplicationContainer:
    """Build the services required by the API application."""
    (
        search_adapter,
        indexed_chunk_count,
        vector_configured,
        vector_reachable,
    ) = build_search_adapter(settings)
    agent_factory = PlatformKnowledgeAgentFactory(
        api_key=settings.openai_api_key.get_secret_value(),
        model_id=settings.openai_model,
    )

    platform_service = PlatformKnowledgeService(
        agent_factory=agent_factory,
        search_adapter=search_adapter,
    )
    registry = _build_component_registry(settings)
    repository_reader = (
        LocalRepositoryReader(
            maximum_files=settings.repository_maximum_files,
            maximum_file_bytes=settings.repository_maximum_file_bytes,
        )
        if settings.repository_local_root is not None
        and settings.component_registry_directory is not None
        else None
    )
    github_search = (
        _build_github_search_adapter(settings)
        if settings.github_repositories or settings.github_organization
        else None
    )
    github_agent_factory = (
        _build_github_agent_factory(settings) if github_search is not None else None
    )
    unified_service = UnifiedKnowledgeService(
        agent_factory=agent_factory,
        platform_search=search_adapter,
        repository_root=settings.repository_local_root,
        registry=registry if repository_reader is not None else None,
        repository_reader=repository_reader,
        github_agent_factory=github_agent_factory,
        github_search=github_search,
    )
    github_service = (
        GitHubKnowledgeService(
            agent_factory=github_agent_factory,
            search_adapter=github_search,
        )
        if github_agent_factory is not None and github_search is not None
        else None
    )
    return ApplicationContainer(
        platform_knowledge_service=platform_service,
        unified_knowledge_service=unified_service,
        github_knowledge_service=github_service,
        indexed_chunk_count=indexed_chunk_count,
        vector_retrieval_configured=vector_configured,
        vector_retrieval_reachable=vector_reachable,
    )


def build_github_knowledge_service(settings: Settings) -> GitHubKnowledgeService:
    """Build the read-only GitHub Knowledge Agent."""
    return GitHubKnowledgeService(
        agent_factory=_build_github_agent_factory(settings),
        search_adapter=_build_github_search_adapter(settings),
    )


def _build_github_search_adapter(settings: Settings) -> GitHubRepositorySearchAdapter:
    repositories = settings.github_repositories
    organization = settings.github_organization
    if not repositories and organization is None:
        raise ValueError("A GitHub organization or approved repository is required.")
    return GitHubRepositorySearchAdapter(
        client=GitHubCodeClient(
            GitHubClientConfig(
                token=settings.github_token.get_secret_value(),
                api_url=settings.github_api_url,
                api_version=settings.github_api_version,
                maximum_file_bytes=settings.github_maximum_file_bytes,
            )
        ),
        repositories=repositories,
        organization=organization,
        maximum_results=settings.github_maximum_results,
    )


def _build_github_agent_factory(settings: Settings) -> GitHubKnowledgeAgentFactory:
    return GitHubKnowledgeAgentFactory(
        api_key=settings.openai_api_key.get_secret_value(),
        model_id=settings.openai_model,
    )


def build_document_repository(settings: Settings) -> S3DocumentRepository:
    """Build the configured S3 document repository."""
    return S3DocumentRepository(
        s3_client=create_s3_client(settings.aws_region),
        bucket=settings.s3_bucket,
        max_document_size_bytes=settings.max_document_size_bytes,
    )


def build_search_adapter(
    settings: Settings,
) -> tuple[KnowledgeSearchAdapter, int, bool, bool]:
    """Ingest configured documents and build deterministic search."""
    chunks = build_ingestion_service(settings).ingest_prefix(settings.s3_prefix)

    index = KeywordIndex(tokenizer=SearchTokenizer())
    index.build(chunks)

    keyword = KnowledgeSearchService(index=index, minimum_score=0.0)
    semantic = None
    vector_configured = settings.vector_search_enabled and settings.vector_bucket_name is not None
    vector_reachable = False
    if vector_configured:
        vectors = S3VectorsRepository(
            create_s3vectors_client(settings.aws_region),
            settings.vector_bucket_name or "",
            settings.vector_index_name,
            settings.embedding_dimensions,
        )
        vector_reachable = vectors.is_reachable()
        if vector_reachable:
            semantic = SemanticSearchService(
                OpenAIEmbeddingProvider(
                    OpenAIEmbeddingConfig(
                        settings.openai_api_key.get_secret_value(),
                        settings.embedding_model,
                        settings.embedding_dimensions,
                    )
                ),
                vectors,
                S3ChunkRepository(create_s3_client(settings.aws_region), settings.s3_bucket),
                settings.vector_top_k,
            )
    mode = RetrievalMode(settings.retrieval_mode)
    search_adapter = KnowledgeSearchAdapter(
        search_service=HybridSearchService(keyword, semantic, mode),
        maximum_results=settings.agent_max_search_results,
    )
    return search_adapter, len(chunks), vector_configured, vector_reachable


def build_ingestion_service(settings: Settings) -> KnowledgeIngestionService:
    """Build classified document ingestion."""
    return KnowledgeIngestionService(
        repository=build_document_repository(settings),
        parser_registry=DocumentParserRegistry(),
        chunker=DocumentChunker(
            text_splitter=TextSplitter(
                max_characters=CHUNK_MAX_CHARACTERS,
                overlap_characters=CHUNK_OVERLAP_CHARACTERS,
            )
        ),
        classification_service=DocumentClassificationService(_build_component_registry(settings)),
    )


def build_vector_ingestion_service(settings: Settings) -> VectorIngestionService:
    """Build the explicit S3 Vectors ingestion workflow."""
    if not settings.vector_bucket_name:
        raise ValueError("VECTOR_BUCKET_NAME is required for vector ingestion.")
    return VectorIngestionService(
        OpenAIEmbeddingProvider(
            OpenAIEmbeddingConfig(
                settings.openai_api_key.get_secret_value(),
                settings.embedding_model,
                settings.embedding_dimensions,
            )
        ),
        S3ChunkRepository(create_s3_client(settings.aws_region), settings.s3_bucket),
        S3VectorsRepository(
            create_s3vectors_client(settings.aws_region),
            settings.vector_bucket_name,
            settings.vector_index_name,
            settings.embedding_dimensions,
        ),
        settings.embedding_model,
        settings.embedding_dimensions,
        settings.embedding_batch_size,
        chunking_version=settings.chunking_version,
        visual_prompt_version=settings.visual_analysis_prompt_version,
    )


def _build_component_registry(settings: Settings) -> ComponentRegistry:
    directory = settings.component_registry_directory
    return (
        ComponentRegistryLoader().load(directory, allow_empty_placeholders=True)
        if directory
        else ComponentRegistry(())
    )


def build_visual_processing_service(
    settings: Settings,
    *,
    analyser: VisualPageAnalyser | None = None,
) -> VisualDocumentProcessingService:
    """Build selective PDF visual inspection, rendering and analysis."""
    return VisualDocumentProcessingService(
        detector=VisualPageDetector(
            VisualPageDetectorConfig(
                minimum_text_characters=settings.visual_minimum_text_characters,
                minimum_image_area_ratio=settings.visual_minimum_image_area_ratio,
            )
        ),
        renderer=PDFPageRenderer(PDFPageRendererConfig(dpi=settings.visual_render_dpi)),
        analyser=analyser,
        maximum_pages=settings.visual_max_pages_per_document,
    )


def build_pdf_enrichment_service(settings: Settings) -> PDFEnrichmentService:
    """Build PDF enrichment with model-based visual analysis enabled."""
    return PDFEnrichmentService(
        build_visual_processing_service(
            settings,
            analyser=_build_visual_analyser(settings),
        )
    )


def _build_visual_analyser(settings: Settings) -> StrandsVisualPageAnalyser:
    return StrandsVisualPageAnalyser(
        StrandsVisualAnalyserConfig(
            api_key=settings.openai_api_key.get_secret_value(),
            model_id=settings.visual_analysis_model or settings.openai_model,
            prompt_version=settings.visual_analysis_prompt_version,
            maximum_image_bytes=settings.visual_analysis_max_image_bytes,
        )
    )
