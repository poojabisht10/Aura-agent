"""Tests for MCP tools - Component Library."""
import pytest
import json
from backend.mcp_tools.component_library import (
    _search_components_impl as search_components,
    _save_component_impl as save_component,
    _get_component_impl as get_component,
    _reset_store,
)


@pytest.fixture(autouse=True)
def reset_store():
    """Reset component store before each test."""
    _reset_store()
    yield
    _reset_store()


@pytest.mark.asyncio
async def test_save_component():
    """Test saving a component to the library."""
    result = await save_component({
        "name": "PrimaryButton",
        "code": "export const PrimaryButton = ({ children }) => <button className='bg-blue-500'>{children}</button>",
        "description": "A primary button with blue background",
        "category": "button",
        "props_schema": {"children": "ReactNode"}
    })

    content = json.loads(result["content"][0]["text"])
    assert content["success"] is True
    assert content["component_id"] == 1
    assert "PrimaryButton" in content["message"]


@pytest.mark.asyncio
async def test_save_duplicate_component():
    """Test that duplicate component names are rejected."""
    # Save first component
    await save_component({
        "name": "PrimaryButton",
        "code": "export const PrimaryButton = () => <button>Click</button>",
        "description": "A button",
        "category": "button",
    })

    # Try to save duplicate
    result = await save_component({
        "name": "PrimaryButton",
        "code": "export const PrimaryButton = () => <button>Different</button>",
        "description": "Another button",
        "category": "button",
    })

    content = json.loads(result["content"][0]["text"])
    assert content["success"] is False
    assert "already exists" in content["warning"]


@pytest.mark.asyncio
async def test_get_component():
    """Test retrieving a component by ID."""
    # Save a component first
    await save_component({
        "name": "Card",
        "code": "export const Card = ({ title }) => <div className='p-4 rounded'>{title}</div>",
        "description": "A card component",
        "category": "card",
    })

    # Get the component
    result = await get_component({"component_id": 1})

    content = json.loads(result["content"][0]["text"])
    assert content["name"] == "Card"
    assert "Card" in content["code"]
    assert content["category"] == "card"
    assert content["reuse_count"] == 1  # Should increment on retrieval


@pytest.mark.asyncio
async def test_get_nonexistent_component():
    """Test retrieving a component that doesn't exist."""
    result = await get_component({"component_id": 999})

    content = json.loads(result["content"][0]["text"])
    assert "error" in content
    assert "not found" in content["error"]


@pytest.mark.asyncio
async def test_search_components():
    """Test searching for components."""
    # Save some components
    await save_component({
        "name": "PrimaryButton",
        "code": "export const PrimaryButton = () => <button>Primary</button>",
        "description": "A primary button for main actions",
        "category": "button",
    })

    await save_component({
        "name": "SecondaryButton",
        "code": "export const SecondaryButton = () => <button>Secondary</button>",
        "description": "A secondary button for secondary actions",
        "category": "button",
    })

    await save_component({
        "name": "UserCard",
        "code": "export const UserCard = () => <div>User Card</div>",
        "description": "A card displaying user information",
        "category": "card",
    })

    # Search for buttons
    result = await search_components({
        "description": "button",
        "category": "button",
    })

    content = json.loads(result["content"][0]["text"])
    assert content["found_count"] >= 1

    # Check that buttons are found
    component_names = [c["name"] for c in content["components"]]
    assert any("Button" in name for name in component_names)


@pytest.mark.asyncio
async def test_search_with_minimum_similarity():
    """Test search respects minimum similarity threshold."""
    await save_component({
        "name": "PrimaryButton",
        "code": "export const PrimaryButton = () => <button>Primary</button>",
        "description": "A primary button",
        "category": "button",
    })

    # Search with high threshold - should find match
    result = await search_components({
        "description": "primary button",
        "min_similarity": 50,
    })

    content = json.loads(result["content"][0]["text"])
    assert content["found_count"] >= 1

    # Search with very high threshold - might not find match
    result = await search_components({
        "description": "completely unrelated xyz",
        "min_similarity": 90,
    })

    content = json.loads(result["content"][0]["text"])
    assert content["found_count"] == 0


@pytest.mark.asyncio
async def test_save_component_missing_required_fields():
    """Test that saving without required fields fails."""
    # Missing code
    result = await save_component({
        "name": "Button",
        "description": "A button",
    })

    content = json.loads(result["content"][0]["text"])
    assert content["success"] is False
    assert "required" in content["error"]

    # Missing name
    result = await save_component({
        "code": "export const Button = () => <button>Click</button>",
        "description": "A button",
    })

    content = json.loads(result["content"][0]["text"])
    assert content["success"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
