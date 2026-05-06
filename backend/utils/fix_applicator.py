"""Smart fix application for code modifications."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class FixApplicator:
    """Applies fixes to code files with precision."""

    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.applied_fixes = []
        self.failed_fixes = []

    async def apply_fix(self, fix: dict) -> bool:
        """
        Apply a single fix to the codebase.

        Args:
            fix: Fix dictionary with instructions

        Returns:
            True if successful, False otherwise
        """
        fix_type = fix.get("type")
        instructions = fix.get("instructions", {})

        if not instructions:
            print(f"[Fix Applicator] No instructions in fix: {fix}")
            return False

        try:
            if fix_type == "spacing":
                return await self.apply_class_replacement(
                    file_path=Path(instructions["file"]),
                    old_class=instructions["from"],
                    new_class=instructions["to"],
                )

            elif fix_type == "color":
                return await self.apply_style_change(
                    file_path=Path(instructions["file"]),
                    property="backgroundColor",
                    old_value=instructions.get("from", ""),
                    new_value=instructions["to"],
                )

            elif fix_type == "layout":
                return await self.apply_layout_fix(
                    file_path=Path(instructions["file"]),
                    classes=instructions.get("classes", []),
                )

            elif fix_type == "shadow":
                return await self.apply_shadow_fix(
                    file_path=Path(instructions["file"]),
                    shadow_class=instructions.get("shadow_class", ""),
                )

            else:
                print(f"[Fix Applicator] Unknown fix type: {fix_type}")
                return False

        except Exception as e:
            print(f"[Fix Applicator] Error applying fix: {e}")
            self.failed_fixes.append(fix)
            return False

    async def apply_class_replacement(
        self,
        file_path: Path,
        old_class: str,
        new_class: str,
        line_range: Optional[Tuple[int, int]] = None,
    ) -> bool:
        """
        Replace Tailwind class in a specific component.

        Args:
            file_path: Path to file (relative to project)
            old_class: Old Tailwind class (e.g., "p-4")
            new_class: New Tailwind class (e.g., "p-6")
            line_range: Optional line range to limit replacement

        Returns:
            True if successful
        """
        full_path = self.project_path / file_path

        if not full_path.exists():
            print(f"[Fix Applicator] File not found: {full_path}")
            return False

        try:
            content = full_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            # Determine range
            start_line = line_range[0] - 1 if line_range else 0
            end_line = line_range[1] if line_range else len(lines)

            modified = False

            for i in range(start_line, min(end_line, len(lines))):
                # Look for className attribute
                if "className" in lines[i]:
                    # Replace old class with new class
                    old_pattern = r'\b' + re.escape(old_class) + r'\b'
                    if re.search(old_pattern, lines[i]):
                        lines[i] = re.sub(old_pattern, new_class, lines[i])
                        modified = True
                        print(f"[Fix Applicator] Replaced '{old_class}' with '{new_class}' at line {i + 1}")

            if modified:
                full_path.write_text("\n".join(lines), encoding="utf-8")
                self.applied_fixes.append({
                    "file": str(file_path),
                    "type": "class_replacement",
                    "old": old_class,
                    "new": new_class,
                })
                return True

            print(f"[Fix Applicator] Class '{old_class}' not found in {file_path}")
            return False

        except Exception as e:
            print(f"[Fix Applicator] Error in class_replacement: {e}")
            return False

    async def apply_style_change(
        self,
        file_path: Path,
        property: str,
        old_value: str,
        new_value: str,
    ) -> bool:
        """
        Change inline style property.

        Args:
            file_path: Path to file
            property: CSS property name (e.g., "backgroundColor")
            old_value: Old value
            new_value: New value

        Returns:
            True if successful
        """
        full_path = self.project_path / file_path

        if not full_path.exists():
            return False

        try:
            content = full_path.read_text(encoding="utf-8")

            # Pattern to match inline styles
            style_pattern = rf'style\s*=\s*\{{\s*[^}}]*{property}:\s*["\']?{re.escape(old_value)}["\']?'

            if re.search(style_pattern, content):
                content = re.sub(
                    rf'{property}:\s*["\']?{re.escape(old_value)}["\']?',
                    f'{property}: "{new_value}"',
                    content
                )

                full_path.write_text(content, encoding="utf-8")
                self.applied_fixes.append({
                    "file": str(file_path),
                    "type": "style_change",
                    "property": property,
                    "old": old_value,
                    "new": new_value,
                })
                return True

            return False

        except Exception as e:
            print(f"[Fix Applicator] Error in style_change: {e}")
            return False

    async def apply_layout_fix(
        self,
        file_path: Path,
        classes: List[str],
    ) -> bool:
        """
        Add layout classes to fix alignment.

        Args:
            file_path: Path to file
            classes: List of classes to add (e.g., ["flex", "items-center"])

        Returns:
            True if successful
        """
        full_path = self.project_path / file_path

        if not full_path.exists():
            return False

        try:
            content = full_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            modified = False

            # Find className attributes and add classes
            for i, line in enumerate(lines):
                if "className" in line:
                    # Check if classes already exist
                    missing_classes = [c for c in classes if c not in line]

                    if missing_classes:
                        # Add missing classes
                        # Pattern: className="existing classes"
                        pattern = r'className\s*=\s*"([^"]*)"'
                        match = re.search(pattern, line)

                        if match:
                            existing = match.group(1)
                            new_classes = f"{existing} {' '.join(missing_classes)}"
                            lines[i] = re.sub(pattern, f'className="{new_classes}"', line)
                            modified = True
                            print(f"[Fix Applicator] Added classes {missing_classes} at line {i + 1}")
                            break

            if modified:
                full_path.write_text("\n".join(lines), encoding="utf-8")
                self.applied_fixes.append({
                    "file": str(file_path),
                    "type": "layout_fix",
                    "classes": classes,
                })
                return True

            return False

        except Exception as e:
            print(f"[Fix Applicator] Error in layout_fix: {e}")
            return False

    async def apply_shadow_fix(
        self,
        file_path: Path,
        shadow_class: str,
    ) -> bool:
        """
        Add shadow class to element.

        Args:
            file_path: Path to file
            shadow_class: Shadow class to add (e.g., "shadow-lg")

        Returns:
            True if successful
        """
        full_path = self.project_path / file_path

        if not full_path.exists():
            return False

        try:
            content = full_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            modified = False

            # Find className attributes and add shadow
            for i, line in enumerate(lines):
                if "className" in line and "shadow" not in line:
                    # Add shadow class
                    pattern = r'className\s*=\s*"([^"]*)"'
                    match = re.search(pattern, line)

                    if match:
                        existing = match.group(1)
                        new_classes = f"{existing} {shadow_class}"
                        lines[i] = re.sub(pattern, f'className="{new_classes}"', line)
                        modified = True
                        print(f"[Fix Applicator] Added shadow '{shadow_class}' at line {i + 1}")
                        break

            if modified:
                full_path.write_text("\n".join(lines), encoding="utf-8")
                self.applied_fixes.append({
                    "file": str(file_path),
                    "type": "shadow_fix",
                    "shadow_class": shadow_class,
                })
                return True

            return False

        except Exception as e:
            print(f"[Fix Applicator] Error in shadow_fix: {e}")
            return False

    async def verify_fix_applied(self, fix: dict) -> bool:
        """
        Verify that a fix was successfully applied.

        Args:
            fix: Fix dictionary

        Returns:
            True if fix is present in code
        """
        instructions = fix.get("instructions", {})
        file_path = Path(instructions.get("file", ""))
        full_path = self.project_path / file_path

        if not full_path.exists():
            return False

        try:
            content = full_path.read_text(encoding="utf-8")

            # Check based on fix type
            if fix.get("type") == "spacing":
                new_value = instructions.get("to", "")
                return new_value in content

            elif fix.get("type") == "color":
                new_value = instructions.get("to", "")
                return new_value in content

            return True

        except Exception:
            return False

    def get_applied_fixes(self) -> List[Dict]:
        """Get list of successfully applied fixes."""
        return self.applied_fixes

    def get_failed_fixes(self) -> List[Dict]:
        """Get list of fixes that failed to apply."""
        return self.failed_fixes

    def reset(self):
        """Reset applied and failed fixes lists."""
        self.applied_fixes = []
        self.failed_fixes = []
