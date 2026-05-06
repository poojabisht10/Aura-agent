# Use RAG-based component library (ChromaDB)
from .component_library_rag import create_component_library_server

# Legacy in-memory version available as:
# from .component_library import create_component_library_server as create_inmemory_server

__all__ = ["create_component_library_server"]
