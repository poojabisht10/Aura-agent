"""Component Library MCP Tools using ChromaDB RAG for semantic search."""
import json
from typing import Any, Dict

from claude_agent_sdk import tool, create_sdk_mcp_server

from backend.rag import ComponentStore


# Lazy-loaded store instance
_store: ComponentStore = None


def _get_store() -> ComponentStore:
    """Get or create the component store."""
    global _store
    if _store is None:
        _store = ComponentStore()
    return _store


def _reset_store():
    """Reset the component store (for testing)."""
    global _store
    if _store is not None:
        _store.reset()


# Core implementation functions (testable)
async def _search_components_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for similar components using semantic search.
    """
    store = _get_store()

    query = args.get("description", "")
    category = args.get("category")
    min_similarity = args.get("min_similarity", 60) / 100  # Convert to 0-1

    results = store.search_similar(
        query=query,
        category=category,
        n_results=10,
        min_similarity=min_similarity,
    )

    # Format results
    components = []
    for comp in results:
        components.append({
            "id": comp["id"],
            "name": comp["name"],
            "description": comp["description"],
            "category": comp["category"],
            "similarity_score": int(comp["similarity"] * 100),
            "reuse_recommendation": comp["reuse_recommendation"],
            "code_preview": comp["code"][:500] + "..." if len(comp["code"]) > 500 else comp["code"],
        })

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "found_count": len(components),
                "components": components,
                "total_in_library": store.count(),
                "suggestion": "Use get_component to retrieve full code for any component"
            }, indent=2)
        }]
    }


async def _save_component_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save a new component to the RAG store.
    """
    store = _get_store()

    name = args.get("name", "")
    code = args.get("code", "")
    description = args.get("description", "")
    category = args.get("category", "other")
    props_schema = args.get("props_schema", {})

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

    # Check for existing similar components
    existing = store.search_similar(
        query=f"{name} {description}",
        category=category,
        n_results=1,
        min_similarity=0.95,  # Very high similarity = likely duplicate
    )

    if existing and existing[0]["name"] == name:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "warning": f"Component '{name}' already exists with ID {existing[0]['id']}",
                    "existing_id": existing[0]["id"],
                    "success": False
                })
            }]
        }

    # Add to store
    component_id = store.add_component(
        name=name,
        code=code,
        description=description,
        category=category,
        props_schema=props_schema,
    )

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "component_id": component_id,
                "message": f"Component '{name}' saved successfully",
                "total_components": store.count()
            }, indent=2)
        }]
    }


async def _get_component_impl(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get full component details by ID.
    """
    store = _get_store()

    component_id = args.get("component_id")

    if component_id is None:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({"error": "component_id is required"})
            }]
        }

    component = store.get_component(str(component_id))

    if not component:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "error": f"Component with ID {component_id} not found",
                    "total_components": store.count()
                })
            }]
        }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "id": component["id"],
                "name": component["name"],
                "code": component["code"],
                "description": component["description"],
                "category": component["category"],
                "props_schema": component["props_schema"],
            }, indent=2)
        }]
    }


# MCP Tool decorators
@tool(
    "search_components",
    "Search the component library for similar components using semantic search (RAG)",
    {"description": str, "category": str, "min_similarity": int}
)
async def search_components(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _search_components_impl(args)


@tool(
    "save_component",
    "Save a new component to the RAG-based library for future reuse",
    {"name": str, "code": str, "description": str, "category": str, "props_schema": dict}
)
async def save_component(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _save_component_impl(args)


@tool(
    "get_component",
    "Retrieve full component code by ID from the RAG store",
    {"component_id": str}
)
async def get_component(args: Dict[str, Any]) -> Dict[str, Any]:
    return await _get_component_impl(args)


def create_component_library_server():
    """Create the RAG-based component library MCP server."""
    return create_sdk_mcp_server(
        name="component_library",
        version="2.0.0",  # Version 2 uses RAG
        tools=[search_components, save_component, get_component]
    )
