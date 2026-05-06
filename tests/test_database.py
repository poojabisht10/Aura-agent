"""Tests for database models and operations."""
import pytest
import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base, Project, Component, ComponentUsage


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Create a test database session."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_project(db_session):
    """Test creating a project."""
    project = Project(
        name="test-project",
        figma_url="https://figma.com/file/abc123",
        status="pending",
    )

    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    assert project.id is not None
    assert project.name == "test-project"
    assert project.status == "pending"
    assert project.created_at is not None


@pytest.mark.asyncio
async def test_create_component(db_session):
    """Test creating a component."""
    # First create a project
    project = Project(
        name="test-project",
        figma_url="https://figma.com/file/abc123",
    )
    db_session.add(project)
    await db_session.commit()

    # Create component
    component = Component(
        name="PrimaryButton",
        code="export const PrimaryButton = () => <button>Click</button>",
        description="A primary button",
        category="button",
        project_id=project.id,
    )

    db_session.add(component)
    await db_session.commit()
    await db_session.refresh(component)

    assert component.id is not None
    assert component.name == "PrimaryButton"
    assert component.category == "button"
    assert component.reuse_count == 0


@pytest.mark.asyncio
async def test_component_usage_tracking(db_session):
    """Test tracking component usage across projects."""
    # Create two projects
    project1 = Project(name="project-1", figma_url="https://figma.com/file/1")
    project2 = Project(name="project-2", figma_url="https://figma.com/file/2")
    db_session.add_all([project1, project2])
    await db_session.commit()

    # Create component in project1
    component = Component(
        name="SharedButton",
        code="export const SharedButton = () => <button>Shared</button>",
        category="button",
        project_id=project1.id,
    )
    db_session.add(component)
    await db_session.commit()

    # Track reuse in project2
    usage = ComponentUsage(
        component_id=component.id,
        project_id=project2.id,
        was_modified=False,
    )
    db_session.add(usage)
    await db_session.commit()

    assert usage.id is not None
    assert usage.component_id == component.id
    assert usage.project_id == project2.id


@pytest.mark.asyncio
async def test_project_status_update(db_session):
    """Test updating project status."""
    project = Project(
        name="test-project",
        figma_url="https://figma.com/file/abc123",
        status="pending",
    )
    db_session.add(project)
    await db_session.commit()

    # Update status
    project.status = "completed"
    project.components_generated = 5
    project.components_reused = 2
    project.conversion_time_seconds = 45.5
    await db_session.commit()

    await db_session.refresh(project)
    assert project.status == "completed"
    assert project.components_generated == 5
    assert project.components_reused == 2
    assert project.conversion_time_seconds == 45.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
