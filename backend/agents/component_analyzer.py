"""Component similarity analysis using embeddings."""
import json
import os
from typing import List, Dict, Any, Optional
import numpy as np

from claude_agent_sdk import query, ClaudeAgentOptions

from backend.config import settings


def _ensure_litellm_configured():
    """Ensure LiteLLM environment variables are set."""
    if not os.environ.get("ANTHROPIC_BASE_URL"):
        os.environ["ANTHROPIC_BASE_URL"] = settings.litellm_base_url
        os.environ["ANTHROPIC_API_KEY"] = settings.litellm_api_key


class ComponentAnalyzer:
    """Analyzes components for similarity and reuse potential."""

    def __init__(self, use_embeddings: bool = True):
        self.use_embeddings = use_embeddings
        self._model = None

    @property
    def embedding_model(self):
        """Lazy load the sentence transformer model."""
        if self._model is None and self.use_embeddings:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                print("Warning: sentence-transformers not installed. Using LLM-based analysis.")
                self.use_embeddings = False
        return self._model

    def generate_embedding(self, component_data: Dict[str, Any]) -> Optional[np.ndarray]:
        """Generate embedding vector for a component."""
        if not self.use_embeddings or self.embedding_model is None:
            return None

        # Combine relevant fields into text for embedding
        text_parts = [
            component_data.get("name", ""),
            component_data.get("description", ""),
            component_data.get("category", ""),
            json.dumps(component_data.get("props_schema", {})),
        ]
        text = " ".join(filter(None, text_parts))

        embedding = self.embedding_model.encode(text)
        return embedding

    def embedding_to_string(self, embedding: np.ndarray) -> str:
        """Convert embedding array to comma-separated string for storage."""
        return ",".join(map(str, embedding.tolist()))

    def string_to_embedding(self, embedding_str: str) -> np.ndarray:
        """Convert stored string back to numpy array."""
        return np.array([float(x) for x in embedding_str.split(",")])

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))

    def find_similar_components(
        self,
        query_component: Dict[str, Any],
        existing_components: List[Dict[str, Any]],
        threshold: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """
        Find components similar to the query component.

        Args:
            query_component: Component to find matches for
            existing_components: List of existing components with embedding_vector field
            threshold: Minimum similarity score (0-1)

        Returns:
            List of similar components with similarity scores
        """
        query_embedding = self.generate_embedding(query_component)

        if query_embedding is None:
            # Fall back to LLM-based analysis
            return self._llm_based_similarity(query_component, existing_components)

        similar = []
        for comp in existing_components:
            if not comp.get("embedding_vector"):
                continue

            stored_embedding = self.string_to_embedding(comp["embedding_vector"])
            similarity = self.cosine_similarity(query_embedding, stored_embedding)

            if similarity >= threshold:
                similar.append({
                    "component": comp,
                    "similarity": similarity,
                    "reuse_recommendation": self._get_recommendation(similarity),
                })

        # Sort by similarity descending
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        return similar

    def _get_recommendation(self, similarity: float) -> str:
        """Get reuse recommendation based on similarity score."""
        if similarity >= 0.9:
            return "reuse_directly"
        elif similarity >= 0.8:
            return "reuse_with_minor_modifications"
        elif similarity >= 0.6:
            return "consider_modifying"
        else:
            return "create_new"

    async def _llm_based_similarity(
        self,
        query_component: Dict[str, Any],
        existing_components: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Fall back to LLM-based similarity analysis using LiteLLM."""
        if not existing_components:
            return []

        # Ensure LiteLLM is configured
        _ensure_litellm_configured()

        # Use Claude Haiku for fast analysis via LiteLLM
        options = ClaudeAgentOptions(
            model=settings.fast_model,
            max_turns=1,
        )

        prompt = f"""Analyze the similarity between the NEW component and EXISTING components.
Return JSON array with similarity scores (0-100) for each existing component.

NEW COMPONENT:
{json.dumps(query_component, indent=2)}

EXISTING COMPONENTS:
{json.dumps([{
    "id": c.get("id"),
    "name": c.get("name"),
    "description": c.get("description"),
    "category": c.get("category")
} for c in existing_components[:10]], indent=2)}

Return ONLY valid JSON array like:
[{{"id": 1, "similarity": 85}}, {{"id": 2, "similarity": 45}}]"""

        result_text = ""
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, "content"):
                for block in message.content:
                    if hasattr(block, "text"):
                        result_text += block.text

        try:
            similarities = json.loads(result_text)
            similar = []
            for sim in similarities:
                if sim["similarity"] >= 60:
                    comp = next(
                        (c for c in existing_components if c.get("id") == sim["id"]),
                        None
                    )
                    if comp:
                        similar.append({
                            "component": comp,
                            "similarity": sim["similarity"] / 100,
                            "reuse_recommendation": self._get_recommendation(sim["similarity"] / 100),
                        })
            return similar
        except (json.JSONDecodeError, KeyError):
            return []
