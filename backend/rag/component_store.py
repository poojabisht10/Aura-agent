"""RAG-based Component Store using ChromaDB for semantic search."""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings


class ComponentStore:
    """
    Vector-based component storage using ChromaDB.
    Provides semantic search for finding similar components.
    """

    def __init__(self, persist_directory: str = "./component_library/chroma"):
        """
        Initialize ChromaDB client and collection.

        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB with persistence
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Get or create the components collection
        # Using default embedding function (sentence-transformers)
        self.collection = self.client.get_or_create_collection(
            name="react_components",
            metadata={"description": "Reusable React components with Tailwind CSS"}
        )

    def add_component(
        self,
        name: str,
        code: str,
        description: str,
        category: str,
        props_schema: Optional[Dict] = None,
        figma_metadata: Optional[Dict] = None,
    ) -> str:
        """
        Add a component to the vector store.

        Args:
            name: Component name (e.g., PrimaryButton)
            code: Full React component code
            description: What the component does
            category: Component category (button, card, form, etc.)
            props_schema: TypeScript interface for props
            figma_metadata: Original Figma node data

        Returns:
            Component ID
        """
        # Generate unique ID
        component_id = f"{category}_{name}_{self.collection.count()}"

        # Create document text for embedding (semantic content)
        document = self._create_document(name, description, category, props_schema)

        # Store metadata (non-semantic data)
        metadata = {
            "name": name,
            "category": category,
            "description": description[:500] if description else "",
            "code_length": len(code),
            "has_props": bool(props_schema),
            "usage_count": 0,  # Track how many times component is reused
        }

        # Store full data as JSON in a separate field
        full_data = {
            "code": code,
            "props_schema": props_schema or {},
            "figma_metadata": figma_metadata or {},
        }

        # Add to collection
        self.collection.add(
            ids=[component_id],
            documents=[document],
            metadatas=[metadata],
        )

        # Store full code in a separate file (ChromaDB metadata has size limits)
        self._save_component_code(component_id, full_data)

        return component_id

    def search_similar(
        self,
        query: str,
        category: Optional[str] = None,
        n_results: int = 10,
        min_similarity: float = 0.6,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar components using semantic similarity.

        Args:
            query: Description of what you're looking for
            category: Optional category filter
            n_results: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of matching components with similarity scores
        """
        # Build where filter
        where_filter = None
        if category:
            where_filter = {"category": category}

        # Guard: ChromaDB errors when n_results > collection size or collection is empty
        if self.collection.count() == 0:
            return []

        n_results = min(n_results, self.collection.count())

        # Query the collection
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Process results
        components = []
        if results["ids"] and results["ids"][0]:
            for i, component_id in enumerate(results["ids"][0]):
                # ChromaDB returns L2 distance, convert to similarity
                # Similarity = 1 / (1 + distance)
                distance = results["distances"][0][i] if results["distances"] else 0
                similarity = 1 / (1 + distance)

                if similarity >= min_similarity:
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}

                    # Load full component data
                    full_data = self._load_component_code(component_id)

                    components.append({
                        "id": component_id,
                        "name": metadata.get("name", ""),
                        "description": metadata.get("description", ""),
                        "category": metadata.get("category", ""),
                        "similarity": round(similarity, 3),
                        "reuse_recommendation": self._get_recommendation(similarity),
                        "code": full_data.get("code", ""),
                        "props_schema": full_data.get("props_schema", {}),
                    })

        return components

    def get_component(self, component_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a component by ID.

        Args:
            component_id: The component ID

        Returns:
            Component data or None if not found
        """
        try:
            results = self.collection.get(
                ids=[component_id],
                include=["documents", "metadatas"],
            )

            if not results["ids"]:
                return None

            metadata = results["metadatas"][0] if results["metadatas"] else {}
            full_data = self._load_component_code(component_id)

            return {
                "id": component_id,
                "name": metadata.get("name", ""),
                "description": metadata.get("description", ""),
                "category": metadata.get("category", ""),
                "code": full_data.get("code", ""),
                "props_schema": full_data.get("props_schema", {}),
                "figma_metadata": full_data.get("figma_metadata", {}),
            }
        except Exception:
            return None

    def get_component_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a component by name.

        Args:
            name: The component name

        Returns:
            Component data or None if not found
        """
        try:
            results = self.collection.get(
                where={"name": name},
                include=["documents", "metadatas"],
                limit=1,
            )

            if not results["ids"] or len(results["ids"]) == 0:
                return None

            component_id = results["ids"][0]
            metadata = results["metadatas"][0] if results["metadatas"] else {}
            full_data = self._load_component_code(component_id)

            return {
                "id": component_id,
                "name": metadata.get("name", ""),
                "description": metadata.get("description", ""),
                "category": metadata.get("category", ""),
                "code": full_data.get("code", ""),
                "props_schema": full_data.get("props_schema", {}),
                "figma_metadata": full_data.get("figma_metadata", {}),
                "usage_count": metadata.get("usage_count", 0),
            }
        except Exception:
            return None

    def list_components(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List all components, optionally filtered by category.

        Args:
            category: Optional category filter
            limit: Maximum number of results

        Returns:
            List of component summaries
        """
        where_filter = None
        if category:
            where_filter = {"category": category}

        results = self.collection.get(
            where=where_filter,
            limit=limit,
            include=["metadatas"],
        )

        components = []
        if results["ids"]:
            for i, component_id in enumerate(results["ids"]):
                metadata = results["metadatas"][i] if results["metadatas"] else {}
                full_data = self._load_component_code(component_id)
                components.append({
                    "id": component_id,
                    "name": metadata.get("name", ""),
                    "description": metadata.get("description", ""),
                    "category": metadata.get("category", ""),
                    "code": full_data.get("code", ""),
                    "usage_count": metadata.get("usage_count", 0),
                })

        return components

    def count(self) -> int:
        """Get total number of components in the store."""
        return self.collection.count()

    def increment_usage(self, component_id: str, project_id: Optional[int] = None) -> bool:
        """
        Increment usage count for a component when it's reused.

        Args:
            component_id: The component ID
            project_id: Optional project ID that's using this component

        Returns:
            True if updated, False if component not found
        """
        try:
            # Get current component
            results = self.collection.get(
                ids=[component_id],
                include=["metadatas"],
            )

            if not results["ids"]:
                return False

            # Get current metadata
            metadata = results["metadatas"][0] if results["metadatas"] else {}
            current_usage = metadata.get("usage_count", 0)

            # Update metadata with incremented usage count
            updated_metadata = metadata.copy()
            updated_metadata["usage_count"] = current_usage + 1

            # Update in ChromaDB (need to get document to update)
            # ChromaDB doesn't support partial updates, so we need to get and re-add
            full_results = self.collection.get(
                ids=[component_id],
                include=["documents", "metadatas"],
            )

            if full_results["ids"]:
                document = full_results["documents"][0] if full_results["documents"] else ""
                # Update the collection
                self.collection.update(
                    ids=[component_id],
                    metadatas=[updated_metadata],
                    documents=[document],
                )

            # Track project usage in code file
            if project_id is not None:
                full_data = self._load_component_code(component_id)
                if "used_in_projects" not in full_data:
                    full_data["used_in_projects"] = []
                if project_id not in full_data["used_in_projects"]:
                    full_data["used_in_projects"].append(project_id)
                    self._save_component_code(component_id, full_data)

            return True
        except Exception as e:
            print(f"[Warning] Failed to increment usage for {component_id}: {e}")
            return False

    def get_total_reuse_count(self) -> int:
        """
        Get total number of component reuses across all components.

        Returns:
            Total reuse count
        """
        try:
            # Get all components
            results = self.collection.get(
                include=["metadatas"],
            )

            total = 0
            if results["metadatas"]:
                for metadata in results["metadatas"]:
                    total += metadata.get("usage_count", 0)

            return total
        except Exception:
            return 0

    def delete_component(self, component_id: str) -> bool:
        """
        Delete a component by ID.

        Args:
            component_id: The component ID

        Returns:
            True if deleted, False if not found
        """
        try:
            self.collection.delete(ids=[component_id])
            # Also delete code file
            code_file = self.persist_directory / "codes" / f"{component_id}.json"
            if code_file.exists():
                code_file.unlink()
            return True
        except Exception:
            return False

    def reset(self):
        """Reset the entire component store (use with caution!)."""
        self.client.delete_collection("react_components")
        self.collection = self.client.create_collection(
            name="react_components",
            metadata={"description": "Reusable React components with Tailwind CSS"}
        )
        # Clear code files
        codes_dir = self.persist_directory / "codes"
        if codes_dir.exists():
            for f in codes_dir.glob("*.json"):
                f.unlink()

    def get_reuse_stats(self) -> dict:
        """Return reuse statistics for the component library."""
        try:
            results = self.collection.get(include=["metadatas"])
            total = len(results["ids"]) if results["ids"] else 0
            usage_counts = []
            components_with_usage = 0

            if results["metadatas"]:
                for metadata in results["metadatas"]:
                    count = metadata.get("usage_count", 0)
                    usage_counts.append(count)
                    if count > 0:
                        components_with_usage += 1

            # Build top 10 most-reused components
            top_reused = []
            if results["ids"] and results["metadatas"]:
                paired = list(zip(results["ids"], results["metadatas"]))
                paired.sort(key=lambda x: x[1].get("usage_count", 0), reverse=True)
                for comp_id, metadata in paired[:10]:
                    if metadata.get("usage_count", 0) > 0:
                        top_reused.append({
                            "id": comp_id,
                            "name": metadata.get("name", ""),
                            "category": metadata.get("category", ""),
                            "usage_count": metadata.get("usage_count", 0),
                        })

            avg_usage = sum(usage_counts) / len(usage_counts) if usage_counts else 0.0

            return {
                "total_components": total,
                "components_with_usage": components_with_usage,
                "top_reused": top_reused,
                "average_usage_count": round(avg_usage, 2),
            }
        except Exception as e:
            return {
                "total_components": 0,
                "components_with_usage": 0,
                "top_reused": [],
                "average_usage_count": 0.0,
                "error": str(e),
            }

    def track_decision(self, component_id: str, decision: str, project_id: int) -> bool:
        """
        Record whether a component was reused, adapted, or created_new.

        Args:
            component_id: The component ID
            decision: One of "reused", "adapted", "created_new"
            project_id: The project ID making this decision

        Returns:
            True if recorded, False on error
        """
        valid_decisions = ("reused", "adapted", "created_new")
        if decision not in valid_decisions:
            print(f"[Warning] Invalid decision '{decision}', must be one of {valid_decisions}")
            return False

        try:
            full_data = self._load_component_code(component_id)
            if not full_data:
                return False

            # Initialize decisions list if not present
            if "decisions" not in full_data:
                full_data["decisions"] = []

            full_data["decisions"].append({
                "decision": decision,
                "project_id": project_id,
            })

            self._save_component_code(component_id, full_data)
            return True
        except Exception as e:
            print(f"[Warning] Failed to track decision for {component_id}: {e}")
            return False

    def _create_document(
        self,
        name: str,
        description: str,
        category: str,
        props_schema: Optional[Dict],
    ) -> str:
        """Create document text for embedding."""
        parts = [
            f"Component: {name}",
            f"Category: {category}",
            f"Description: {description}",
        ]

        # Defensive: handle props_schema being None, empty string, or dict
        if props_schema and isinstance(props_schema, dict) and len(props_schema) > 0:
            props_list = ", ".join(props_schema.keys())
            parts.append(f"Props: {props_list}")

        return " | ".join(parts)

    def _save_component_code(self, component_id: str, data: Dict[str, Any]):
        """Save component code to file."""
        codes_dir = self.persist_directory / "codes"
        codes_dir.mkdir(exist_ok=True)

        code_file = codes_dir / f"{component_id}.json"
        with open(code_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_component_code(self, component_id: str) -> Dict[str, Any]:
        """Load component code from file."""
        code_file = self.persist_directory / "codes" / f"{component_id}.json"
        if code_file.exists():
            with open(code_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _get_recommendation(self, similarity: float) -> str:
        """Get reuse recommendation based on similarity score."""
        if similarity >= 0.85:
            return "reuse_directly"
        elif similarity >= 0.8:
            return "reuse_with_minor_modifications"
        elif similarity >= 0.7:
            return "consider_adapting"
        elif similarity >= 0.6:
            return "review_for_ideas"
        else:
            return "create_new"


# Singleton instance for the application
_store_instance: Optional[ComponentStore] = None


def get_component_store(persist_directory: str = "./component_library/chroma") -> ComponentStore:
    """Get or create the singleton ComponentStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = ComponentStore(persist_directory)
    return _store_instance
