"""SQLAlchemy database models for Aura2."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime, Boolean, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Project(Base):
    """Represents a generated React project from Figma."""
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    figma_url = Column(Text, nullable=False)
    figma_file_key = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    project_path = Column(Text)
    status = Column(String(50), default="pending")  # pending, generating, completed, failed
    error_message = Column(Text)

    # Metadata from conversion
    components_generated = Column(Integer, default=0)
    components_reused = Column(Integer, default=0)
    conversion_time_seconds = Column(Float)

    # Multi-page support
    parent_project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    is_page = Column(Boolean, default=False)
    route_path = Column(String(255), nullable=True)  # e.g., "/about"

    # Relationships
    components = relationship("Component", back_populates="project")
    parent = relationship("Project", remote_side=[id], foreign_keys=[parent_project_id], backref="pages")

    def __repr__(self):
        return f"<Project(name='{self.name}', status='{self.status}')>"


class Component(Base):
    """Represents a reusable React component in the library."""
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    code = Column(Text, nullable=False)  # React component code
    description = Column(Text)
    category = Column(String(100))  # button, form, card, layout, etc.

    # Component metadata
    props_schema = Column(JSON)  # TypeScript interface as JSON
    tailwind_classes = Column(JSON)  # Array of Tailwind classes used
    figma_metadata = Column(JSON)  # Original Figma node data

    # Vector embedding for similarity search (stored as comma-separated string)
    embedding_vector = Column(Text)

    # Source tracking
    project_id = Column(Integer, ForeignKey("projects.id"))
    project = relationship("Project", back_populates="components")

    # Usage statistics
    reuse_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Component(name='{self.name}', category='{self.category}')>"


class ComponentUsage(Base):
    """Tracks component reuse across projects."""
    __tablename__ = "component_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    component_id = Column(Integer, ForeignKey("components.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    was_modified = Column(Boolean, default=False)
    modifications = Column(JSON)  # Description of modifications made
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ComponentUsage(component_id={self.component_id}, project_id={self.project_id})>"
