"""Component matching utilities using embeddings."""
import json
from typing import List, Dict, Any, Optional
import numpy as np


class ComponentMatcher:
    """Matches components using vector similarity."""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        """Lazy load sentence transformer model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for component matching. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    def generate_embedding(self, component_data: Dict[str, Any]) -> np.ndarray:
        """Generate embedding for a component."""
        # Combine description, props, and code structure into text
        text_parts = [
            component_data.get("name", ""),
            component_data.get("description", ""),
            f"Category: {component_data.get('category', '')}",
            f"Props: {json.dumps(component_data.get('props_schema', {}))}",
        ]
        text = " ".join(filter(None, text_parts))
        return self.model.encode(text)

    def find_similar_components(
        self,
        query_component: Dict[str, Any],
        existing_components: List[Dict[str, Any]],
        threshold: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        Find components with similarity >= threshold.

        Args:
            query_component: Component to find matches for
            existing_components: List of components with embedding_vector field
            threshold: Minimum cosine similarity (0-1)

        Returns:
            List of matching components with similarity scores
        """
        query_embedding = self.generate_embedding(query_component)

        similar = []
        for comp in existing_components:
            if not comp.get("embedding_vector"):
                continue

            stored_embedding = np.fromstring(comp["embedding_vector"], sep=",")
            similarity = self._cosine_similarity(query_embedding, stored_embedding)

            if similarity >= threshold:
                similar.append({
                    "component": comp,
                    "similarity": float(similarity),
                    "reuse_recommendation": self._get_recommendation(similarity),
                })

        return sorted(similar, key=lambda x: x["similarity"], reverse=True)

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def _get_recommendation(self, similarity: float) -> str:
        """Get reuse recommendation based on similarity."""
        if similarity >= 0.9:
            return "reuse_directly"
        elif similarity >= 0.8:
            return "reuse_with_minor_changes"
        elif similarity >= 0.6:
            return "consider_modifying"
        else:
            return "create_new"
