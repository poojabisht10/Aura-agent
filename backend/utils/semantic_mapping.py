"""Semantic mapping between Figma nodes and React components."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import ast


class ComponentLocation:
    """Represents the location of a component in the codebase."""

    def __init__(self, file_path: Path, component_name: str, line_start: int, line_end: int):
        self.file_path = file_path
        self.component_name = component_name
        self.line_start = line_start
        self.line_end = line_end

    def __repr__(self):
        return f"ComponentLocation({self.component_name} @ {self.file_path}:{self.line_start}-{self.line_end})"


class ComponentMapping:
    """Mapping between Figma node and React component."""

    def __init__(
        self,
        node_id: str,
        node_name: str,
        component_name: str,
        file_path: Path,
        line_range: Tuple[int, int],
        props: Optional[Dict] = None,
    ):
        self.node_id = node_id
        self.node_name = node_name
        self.component_name = component_name
        self.file_path = file_path
        self.line_range = line_range
        self.props = props or {}

    def __repr__(self):
        return f"ComponentMapping({self.node_name} -> {self.component_name})"


class SemanticElementMapper:
    """Maps Figma nodes to React components with exact properties."""

    def __init__(self, design_data: dict, project_path: Path):
        self.design_data = design_data
        self.project_path = project_path
        self.component_locations = self._scan_components()
        self.node_to_component = {}

    def _scan_components(self) -> Dict[str, ComponentLocation]:
        """
        Scan project for all React components and their locations.

        Returns:
            Dict mapping component_name to ComponentLocation
        """
        components = {}
        src_dir = self.project_path / "src"

        if not src_dir.exists():
            return components

        # Scan all .tsx and .jsx files
        for file_path in src_dir.rglob("*.tsx"):
            found = self._extract_components_from_file(file_path)
            components.update(found)

        for file_path in src_dir.rglob("*.jsx"):
            found = self._extract_components_from_file(file_path)
            components.update(found)

        print(f"[Semantic Mapper] Found {len(components)} components in project")
        return components

    def _extract_components_from_file(self, file_path: Path) -> Dict[str, ComponentLocation]:
        """
        Extract component names and line numbers from a React file.

        Args:
            file_path: Path to .tsx/.jsx file

        Returns:
            Dict mapping component_name to ComponentLocation
        """
        components = {}

        try:
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Find component declarations
            # Patterns:
            # - const ComponentName = () => {
            # - function ComponentName() {
            # - export default function ComponentName() {
            # - export const ComponentName = () => {

            component_pattern = r"(?:export\s+)?(?:default\s+)?(?:const|function)\s+([A-Z][a-zA-Z0-9]*)\s*(?:=|[:\(])"

            for i, line in enumerate(lines, start=1):
                match = re.search(component_pattern, line)
                if match:
                    component_name = match.group(1)

                    # Find end of component (simplified heuristic)
                    end_line = self._find_component_end(lines, i - 1)

                    components[component_name] = ComponentLocation(
                        file_path=file_path,
                        component_name=component_name,
                        line_start=i,
                        line_end=end_line,
                    )

        except Exception as e:
            print(f"[Semantic Mapper] Error parsing {file_path}: {e}")

        return components

    def _find_component_end(self, lines: List[str], start_idx: int) -> int:
        """
        Find the end line of a component definition.

        Args:
            lines: List of file lines
            start_idx: Start index (0-based)

        Returns:
            End line number (1-based)
        """
        # Count braces to find matching closing brace
        brace_count = 0
        in_component = False

        for i in range(start_idx, len(lines)):
            line = lines[i]

            # Count opening and closing braces
            brace_count += line.count("{") - line.count("}")

            if "{" in line:
                in_component = True

            if in_component and brace_count == 0:
                return i + 1

        # If we couldn't find the end, estimate based on file length
        return min(start_idx + 50, len(lines))

    def build_mapping(self) -> Dict[str, ComponentMapping]:
        """
        Build complete mapping between Figma nodes and React components.

        Returns:
            Dict mapping node_id to ComponentMapping
        """
        mappings = {}

        # Extract frames from design data
        frames = self.design_data.get("frames", [])

        for frame in frames:
            node_id = frame.get("id", "")
            node_name = frame.get("name", "")

            # Try to find matching component
            component_name = self._infer_component_name(node_name)
            location = self.component_locations.get(component_name)

            if location:
                mappings[node_id] = ComponentMapping(
                    node_id=node_id,
                    node_name=node_name,
                    component_name=component_name,
                    file_path=location.file_path,
                    line_range=(location.line_start, location.line_end),
                )

        self.node_to_component = mappings
        return mappings

    def _infer_component_name(self, node_name: str) -> str:
        """
        Infer React component name from Figma node name.

        Args:
            node_name: Figma node name (e.g., "Header Section", "hero-banner")

        Returns:
            React component name (e.g., "Header", "HeroBanner")
        """
        # Remove special characters and split
        cleaned = re.sub(r"[^\w\s]", "", node_name)
        words = cleaned.split()

        # Convert to PascalCase
        component_name = "".join(word.capitalize() for word in words)

        return component_name

    def find_component_for_node(self, node_id: str) -> Optional[ComponentMapping]:
        """
        Find the React component that corresponds to a Figma node.

        Args:
            node_id: Figma node ID

        Returns:
            ComponentMapping or None
        """
        if not self.node_to_component:
            self.build_mapping()

        return self.node_to_component.get(node_id)

    def get_component_location(self, component_name: str) -> Optional[ComponentLocation]:
        """
        Find file path and line numbers for a component.

        Args:
            component_name: React component name

        Returns:
            ComponentLocation or None
        """
        return self.component_locations.get(component_name)

    def find_component_by_similarity(self, target_name: str, threshold: float = 0.7) -> Optional[ComponentLocation]:
        """
        Find component by fuzzy name matching.

        Args:
            target_name: Target component name
            threshold: Similarity threshold (0-1)

        Returns:
            Best matching ComponentLocation or None
        """
        target_lower = target_name.lower()
        best_match = None
        best_score = 0.0

        for component_name, location in self.component_locations.items():
            # Simple similarity: check if one is substring of other
            name_lower = component_name.lower()

            if target_lower in name_lower or name_lower in target_lower:
                score = min(len(target_lower), len(name_lower)) / max(len(target_lower), len(name_lower))
            else:
                # Levenshtein distance approximation
                score = self._similarity_score(target_lower, name_lower)

            if score > best_score and score >= threshold:
                best_score = score
                best_match = location

        return best_match

    def _similarity_score(self, s1: str, s2: str) -> float:
        """
        Calculate similarity score between two strings.

        Args:
            s1: First string
            s2: Second string

        Returns:
            Similarity score (0-1)
        """
        # Simple character overlap ratio
        s1_set = set(s1)
        s2_set = set(s2)

        intersection = s1_set.intersection(s2_set)
        union = s1_set.union(s2_set)

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def get_all_components(self) -> List[ComponentLocation]:
        """Get list of all components found in project."""
        return list(self.component_locations.values())

    def get_component_file_path(self, component_name: str) -> Optional[Path]:
        """Get file path for a component."""
        location = self.component_locations.get(component_name)
        return location.file_path if location else None
