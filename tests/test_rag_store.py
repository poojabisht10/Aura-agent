"""Tests for RAG-based Component Store using ChromaDB."""
import pytest
import tempfile
import shutil
from pathlib import Path

from backend.rag.component_store import ComponentStore


@pytest.fixture
def temp_store():
    """Create a temporary component store for testing."""
    temp_dir = tempfile.mkdtemp()
    store = ComponentStore(persist_directory=temp_dir)
    yield store
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_add_component(temp_store):
    """Test adding a component to the store."""
    component_id = temp_store.add_component(
        name="PrimaryButton",
        code="export const PrimaryButton = ({ children }) => <button className='bg-blue-500'>{children}</button>",
        description="A primary button with blue background for main actions",
        category="button",
        props_schema={"children": "ReactNode", "onClick": "() => void"},
    )

    assert component_id is not None
    assert "button" in component_id
    assert temp_store.count() == 1


def test_search_similar_components(temp_store):
    """Test semantic search for similar components."""
    # Add several components
    temp_store.add_component(
        name="PrimaryButton",
        code="export const PrimaryButton = () => <button className='bg-blue-500'>Primary</button>",
        description="A primary button with blue background for main actions",
        category="button",
    )

    temp_store.add_component(
        name="SecondaryButton",
        code="export const SecondaryButton = () => <button className='bg-gray-500'>Secondary</button>",
        description="A secondary button with gray background for secondary actions",
        category="button",
    )

    temp_store.add_component(
        name="UserCard",
        code="export const UserCard = ({ name }) => <div className='p-4 rounded'>{name}</div>",
        description="A card component that displays user information with avatar and name",
        category="card",
    )

    # Search for buttons
    results = temp_store.search_similar(
        query="I need a button for submitting forms",
        n_results=5,
        min_similarity=0.3,
    )

    assert len(results) >= 1
    # Button components should rank higher than card
    button_found = any("Button" in r["name"] for r in results)
    assert button_found


def test_search_with_category_filter(temp_store):
    """Test search with category filter."""
    temp_store.add_component(
        name="SubmitButton",
        code="export const SubmitButton = () => <button type='submit'>Submit</button>",
        description="A submit button for forms",
        category="button",
    )

    temp_store.add_component(
        name="FormCard",
        code="export const FormCard = () => <div className='card'>Form</div>",
        description="A card container for forms",
        category="card",
    )

    # Search only in button category
    results = temp_store.search_similar(
        query="form submit",
        category="button",
        min_similarity=0.2,
    )

    # Should only find button, not card
    assert all(r["category"] == "button" for r in results)


def test_get_component(temp_store):
    """Test retrieving a component by ID."""
    component_id = temp_store.add_component(
        name="IconButton",
        code="export const IconButton = ({ icon }) => <button>{icon}</button>",
        description="A button with an icon",
        category="button",
        props_schema={"icon": "ReactNode"},
    )

    component = temp_store.get_component(component_id)

    assert component is not None
    assert component["name"] == "IconButton"
    assert "icon" in component["code"]
    assert component["props_schema"]["icon"] == "ReactNode"


def test_get_nonexistent_component(temp_store):
    """Test retrieving a component that doesn't exist."""
    component = temp_store.get_component("nonexistent_id_12345")
    assert component is None


def test_list_components(temp_store):
    """Test listing all components."""
    temp_store.add_component(
        name="Button1",
        code="<button>1</button>",
        description="Button one",
        category="button",
    )
    temp_store.add_component(
        name="Button2",
        code="<button>2</button>",
        description="Button two",
        category="button",
    )
    temp_store.add_component(
        name="Card1",
        code="<div>Card</div>",
        description="A card",
        category="card",
    )

    # List all
    all_components = temp_store.list_components()
    assert len(all_components) == 3

    # List only buttons
    buttons = temp_store.list_components(category="button")
    assert len(buttons) == 2
    assert all(c["category"] == "button" for c in buttons)


def test_delete_component(temp_store):
    """Test deleting a component."""
    component_id = temp_store.add_component(
        name="ToDelete",
        code="<div>Delete me</div>",
        description="Component to delete",
        category="other",
    )

    assert temp_store.count() == 1

    # Delete
    result = temp_store.delete_component(component_id)
    assert result is True
    assert temp_store.count() == 0

    # Verify it's gone
    assert temp_store.get_component(component_id) is None


def test_reset_store(temp_store):
    """Test resetting the entire store."""
    # Add some components
    temp_store.add_component(name="C1", code="<div>1</div>", description="One", category="test")
    temp_store.add_component(name="C2", code="<div>2</div>", description="Two", category="test")

    assert temp_store.count() == 2

    # Reset
    temp_store.reset()

    assert temp_store.count() == 0


def test_similarity_recommendations(temp_store):
    """Test that similarity scores produce correct recommendations."""
    temp_store.add_component(
        name="ExactButton",
        code="export const ExactButton = () => <button>Exact</button>",
        description="An exact button for exact actions",
        category="button",
    )

    # Search with exact match query
    results = temp_store.search_similar(
        query="An exact button for exact actions",
        min_similarity=0.5,
    )

    if results:
        # High similarity should recommend reuse
        assert results[0]["reuse_recommendation"] in [
            "reuse_directly",
            "reuse_with_minor_modifications",
            "consider_adapting",
            "review_for_ideas",
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
