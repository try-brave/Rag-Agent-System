from app.rag.splitters.semi_structured import split_semi_structured_text
from app.rag.splitters.structured import split_structured_text
from app.rag.splitters.unstructured import SplitChunk, split_unstructured_text

SPLITTER_REGISTRY = {
    'structured': split_structured_text,
    'semi_structured': split_semi_structured_text,
    'unstructured': split_unstructured_text,
}

__all__ = [
    'SplitChunk',
    'SPLITTER_REGISTRY',
    'split_structured_text',
    'split_semi_structured_text',
    'split_unstructured_text',
]
