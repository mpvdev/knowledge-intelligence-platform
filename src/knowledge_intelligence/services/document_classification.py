from knowledge_intelligence.domain.classification import (
    ClassificationMethod,
    DocumentClassification,
)
from knowledge_intelligence.registry.registry import ComponentRegistry


class DocumentClassificationService:
    """Classify documents using curated registry information."""

    def __init__(
        self,
        registry: ComponentRegistry,
    ) -> None:
        self._registry = registry

    def classify(
        self,
        document_key: str,
    ) -> DocumentClassification:
        component = self._registry.resolve_document_key(document_key)

        if component is None:
            return DocumentClassification(classification_method=ClassificationMethod.UNCLASSIFIED)

        return DocumentClassification(
            component_id=component.id,
            component_name=component.name,
            related_component_ids=tuple(
                relationship.target_component_id for relationship in component.relationships
            ),
            tags=tuple(alias.casefold() for alias in component.aliases),
            classification_method=ClassificationMethod.REGISTRY_PREFIX,
        )
