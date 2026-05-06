"""Component Library MCP Tools using persistent ChromaDB storage."""
import json
from typing import Any, Dict, List, Optional

from claude_agent_sdk import tool, create_sdk_mcp_server
from backend.rag.component_store import ComponentStore
from backend.config import settings

# Initialize persistent component store (singleton)
_store: Optional[ComponentStore] = None


def _get_store() -> ComponentStore:
    """Get or create the global component store instance."""
    global _store
    if _store is None:
        persist_dir = settings.component_library_dir / "chroma"
        _store = ComponentStore(persist_directory=str(persist_dir))
        print(f"[Component Library] Initialized ChromaDB at {persist_dir}")
    return _store


def _reset_store():
    """Reset the component store (for testing only)."""
    global _store
    if _store:
        _store.reset()
        print("[Component Library] Store reset")


# Core implementation functions
async def _search_components_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for reusable components in the library using semantic search.
    Returns components with similarity scores and reuse recommendations.
    """
    description = args.get("description", "")
    category = args.get("category")
    min_similarity = args.get("min_similarity", 60) / 100.0  # Convert to 0-1 scale

    if not description:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Description is required for search",
                    "found_count": 0,
                    "components": []
                })
            }]
        }

    try:
        store = _get_store()

        # Search using ChromaDB semantic search
        results = store.search_similar(
            query=description,
            category=category,
            n_results=10,
            min_similarity=min_similarity
        )

        # Format results
        formatted_results = []
        for result in results:
            similarity = result["similarity"]

            formatted_results.append({
                "id": result["id"],
                "name": result["name"],
                "description": result.get("description", ""),
                "category": result.get("category", ""),
                "similarity_score": int(similarity * 100),  # Convert to percentage
                "reuse_recommendation": result.get("reuse_recommendation", _get_recommendation(similarity)),
                "code_preview": result["code"][:500] + "..." if len(result["code"]) > 500 else result["code"],
                "usage_count": 0,  # Will be tracked when component is retrieved
            })

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "found_count": len(formatted_results),
                    "components": formatted_results,
                    "suggestion": "Use get_component to retrieve full code for any component" if formatted_results else "No similar components found. Consider creating and saving a new component."
                }, indent=2)
            }]
        }

    except Exception as e:
        print(f"[Component Library] Search error: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Search failed: {str(e)}",
                    "found_count": 0,
                    "components": []
                })
            }]
        }


async def _save_component_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save a new component to the library for future reuse.
    Returns the component ID for future reference.
    """
    name = args.get("name", "")
    code = args.get("code", "")
    description = args.get("description", "")
    category = args.get("category", "other")
    props_schema_raw = args.get("props_schema", None)

    # Normalize props_schema to dict or None (MCP may send as string)
    props_schema = None
    if props_schema_raw:
        if isinstance(props_schema_raw, dict):
            props_schema = props_schema_raw
        elif isinstance(props_schema_raw, str):
            try:
                props_schema = json.loads(props_schema_raw)
            except json.JSONDecodeError:
                print(f"[Component Library] Invalid props_schema JSON: {props_schema_raw}")
                props_schema = None

    if not name or not code:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "Name and code are required",
                    "success": False
                })
            }]
        }

    try:
        store = _get_store()

        # Check for duplicates by name
        existing = store.get_component_by_name(name)
        if existing:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "warning": f"Component '{name}' already exists",
                        "existing_id": existing["id"],
                        "success": False,
                        "message": "Component already in library. Use existing component or choose a different name."
                    })
                }]
            }

        # Save component
        component_id = store.add_component(
            name=name,
            code=code,
            description=description,
            category=category,
            props_schema=props_schema,
        )

        total_count = store.collection.count()

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": True,
                    "component_id": component_id,
                    "message": f"Component '{name}' saved successfully",
                    "total_components": total_count
                }, indent=2)
            }]
        }

    except Exception as e:
        print(f"[Component Library] Save error: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Failed to save component: {str(e)}",
                    "success": False
                })
            }]
        }


async def _get_component_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get full component details by ID.
    """
    component_id = args.get("component_id")

    if not component_id:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": "component_id is required"
                })
            }]
        }

    try:
        store = _get_store()

        # Get component from store
        component = store.get_component(component_id)

        if not component:
            return {
                "content": [{
                    "type": "text",
                    "text": json.dumps({
                        "error": f"Component with ID {component_id} not found"
                    })
                }]
            }

        # Increment usage count
        store.increment_usage(component_id)

        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "id": component_id,
                    "name": component["name"],
                    "code": component["code"],
                    "description": component["description"],
                    "category": component["category"],
                    "props_schema": component.get("props_schema", {}),
                    "usage_count": component.get("usage_count", 0) + 1
                }, indent=2)
            }]
        }

    except Exception as e:
        print(f"[Component Library] Get error: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Failed to get component: {str(e)}"
                })
            }]
        }


def _get_recommendation(similarity: float) -> str:
    """Get reuse recommendation based on similarity score (0-1 scale)."""
    if similarity >= 0.85:
        return "reuse_directly"
    elif similarity >= 0.8:
        return "reuse_with_minor_modifications"
    elif similarity >= 0.6:
        return "consider_adapting"
    else:
        return "create_new"


# MCP Tool decorators (wrap the implementation functions)
@tool(
    "search_components",
    "Search the component library for reusable components similar to the given description. Uses semantic search with ChromaDB.",
    {"description": str, "category": str, "min_similarity": int}
)
async def search_components(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _search_components_impl(args)


@tool(
    "save_component",
    "Save a new component to the library for future reuse. Component is persisted in ChromaDB.",
    {"name": str, "code": str, "description": str, "category": str, "props_schema": dict}
)
async def save_component(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _save_component_impl(args)


@tool(
    "get_component",
    "Retrieve full component code by ID. Increments usage count.",
    {"component_id": str}
)
async def get_component(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _get_component_impl(args)


async def _get_reuse_report_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return reuse statistics for the current component library.
    """
    try:
        store = _get_store()
        stats = store.get_reuse_stats()

        return {
            "content": [{
                "type": "text",
                "text": json.dumps(stats, indent=2)
            }]
        }
    except Exception as e:
        print(f"[Component Library] Reuse report error: {e}")
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Failed to get reuse report: {str(e)}"
                })
            }]
        }


@tool(
    "get_reuse_report",
    "Return reuse statistics for the current component library including total components, usage counts, and top reused components.",
    {}
)
async def get_reuse_report(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _get_reuse_report_impl(args)


def create_component_library_server():
    """Create the component library MCP server with persistent storage."""
    return create_sdk_mcp_server(
        name="component_library",
        version="2.0.0",
        tools=[search_components, save_component, get_component, get_reuse_report]
    )
