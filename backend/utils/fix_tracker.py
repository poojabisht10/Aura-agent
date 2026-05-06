"""Fix tracking system to avoid redundant changes across iterations."""

from typing import List, Dict, Optional
from datetime import datetime


class FixTracker:
    """Track fixes across iterations to avoid redundant changes."""

    def __init__(self):
        self.applied_fixes: List[Dict] = []
        self.pending_fixes: List[Dict] = []
        self.failed_fixes: List[Dict] = []
        self.iteration_history: List[Dict] = []

    def mark_applied(self, fix: dict, iteration: int = 0):
        """
        Mark a fix as successfully applied.

        Args:
            fix: Fix dictionary
            iteration: Iteration number when fix was applied
        """
        fix_record = {
            **fix,
            "status": "applied",
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
        }
        self.applied_fixes.append(fix_record)

        # Remove from pending if present
        self.pending_fixes = [f for f in self.pending_fixes if f.get("id") != fix.get("id")]

        print(f"[Fix Tracker] Fix marked as applied: {fix.get('type')} - {fix.get('location', 'unknown')}")

    def mark_failed(self, fix: dict, reason: str, iteration: int = 0):
        """
        Mark a fix as failed with reason.

        Args:
            fix: Fix dictionary
            reason: Failure reason
            iteration: Iteration number
        """
        fix_record = {
            **fix,
            "status": "failed",
            "reason": reason,
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
        }
        self.failed_fixes.append(fix_record)

        # Remove from pending
        self.pending_fixes = [f for f in self.pending_fixes if f.get("id") != fix.get("id")]

        print(f"[Fix Tracker] Fix marked as failed: {fix.get('type')} - Reason: {reason}")

    def add_pending(self, fix: dict):
        """
        Add a fix to the pending queue.

        Args:
            fix: Fix dictionary
        """
        # Check if already applied
        if self.is_similar_fix_applied(fix):
            print(f"[Fix Tracker] Similar fix already applied, skipping")
            return

        self.pending_fixes.append(fix)

    def is_similar_fix_applied(self, fix: dict) -> bool:
        """
        Check if a similar fix was already applied.

        Args:
            fix: Fix to check

        Returns:
            True if similar fix exists in applied list
        """
        fix_type = fix.get("type")
        location = fix.get("location", "")
        instructions = fix.get("instructions", {})

        for applied in self.applied_fixes:
            # Same type and location
            if applied.get("type") == fix_type and applied.get("location") == location:
                # Check if fixing the same property
                applied_instructions = applied.get("instructions", {})

                if fix_type == "spacing":
                    # Same file and target element
                    if (applied_instructions.get("file") == instructions.get("file") and
                        applied_instructions.get("target_element") == instructions.get("target_element")):
                        return True

                elif fix_type == "color":
                    # Same file and property
                    if (applied_instructions.get("file") == instructions.get("file") and
                        applied_instructions.get("property") == instructions.get("property")):
                        return True

                elif fix_type == "layout":
                    # Same file
                    if applied_instructions.get("file") == instructions.get("file"):
                        return True

                elif fix_type == "shadow":
                    # Same file
                    if applied_instructions.get("file") == instructions.get("file"):
                        return True

        return False

    def get_pending_fixes(self, priority: Optional[str] = None) -> List[Dict]:
        """
        Get pending fixes, optionally filtered by priority.

        Args:
            priority: Optional priority filter ("high", "medium", "low")

        Returns:
            List of pending fixes
        """
        if priority:
            return [f for f in self.pending_fixes if f.get("priority") == priority]
        return self.pending_fixes.copy()

    def get_summary(self) -> Dict:
        """
        Get summary of fixes.

        Returns:
            {
                "total_applied": int,
                "total_failed": int,
                "total_pending": int,
                "by_type": {...},
                "success_rate": float
            }
        """
        # Count by type
        by_type = {}
        for fix in self.applied_fixes:
            fix_type = fix.get("type", "unknown")
            by_type[fix_type] = by_type.get(fix_type, 0) + 1

        # Calculate success rate
        total_attempted = len(self.applied_fixes) + len(self.failed_fixes)
        success_rate = len(self.applied_fixes) / total_attempted if total_attempted > 0 else 0.0

        return {
            "total_applied": len(self.applied_fixes),
            "total_failed": len(self.failed_fixes),
            "total_pending": len(self.pending_fixes),
            "by_type": by_type,
            "success_rate": success_rate,
        }

    def record_iteration(self, iteration: int, fixes_attempted: int, fixes_successful: int):
        """
        Record iteration statistics.

        Args:
            iteration: Iteration number
            fixes_attempted: Number of fixes attempted
            fixes_successful: Number successful
        """
        self.iteration_history.append({
            "iteration": iteration,
            "fixes_attempted": fixes_attempted,
            "fixes_successful": fixes_successful,
            "success_rate": fixes_successful / fixes_attempted if fixes_attempted > 0 else 0,
            "timestamp": datetime.now().isoformat(),
        })

    def get_iteration_history(self) -> List[Dict]:
        """Get complete iteration history."""
        return self.iteration_history.copy()

    def clear_pending(self):
        """Clear all pending fixes."""
        self.pending_fixes = []

    def reset(self):
        """Reset all tracking data."""
        self.applied_fixes = []
        self.pending_fixes = []
        self.failed_fixes = []
        self.iteration_history = []
        print("[Fix Tracker] Reset complete")

    def get_failed_fix_summary(self) -> List[Dict]:
        """
        Get summary of failed fixes with reasons.

        Returns:
            List of failed fix summaries
        """
        summary = []
        for fix in self.failed_fixes:
            summary.append({
                "type": fix.get("type"),
                "location": fix.get("location"),
                "reason": fix.get("reason"),
                "iteration": fix.get("iteration"),
            })
        return summary

    def should_retry_fix(self, fix: dict) -> bool:
        """
        Determine if a failed fix should be retried.

        Args:
            fix: Fix dictionary

        Returns:
            True if should retry
        """
        # Check if this fix has failed before
        fail_count = sum(
            1 for f in self.failed_fixes
            if f.get("type") == fix.get("type") and f.get("location") == fix.get("location")
        )

        # Don't retry if failed more than 2 times
        return fail_count < 2

    def export_report(self) -> str:
        """
        Export a text report of all fixes.

        Returns:
            Formatted text report
        """
        summary = self.get_summary()

        report_lines = [
            "=" * 60,
            "FIX TRACKER REPORT",
            "=" * 60,
            "",
            f"Applied: {summary['total_applied']}",
            f"Failed: {summary['total_failed']}",
            f"Pending: {summary['total_pending']}",
            f"Success Rate: {summary['success_rate']:.1%}",
            "",
            "By Type:",
        ]

        for fix_type, count in summary['by_type'].items():
            report_lines.append(f"  - {fix_type}: {count}")

        report_lines.extend([
            "",
            "Iteration History:",
        ])

        for iteration in self.iteration_history:
            report_lines.append(
                f"  Iteration {iteration['iteration']}: "
                f"{iteration['fixes_successful']}/{iteration['fixes_attempted']} succeeded "
                f"({iteration['success_rate']:.1%})"
            )

        if self.failed_fixes:
            report_lines.extend([
                "",
                "Failed Fixes:",
            ])
            for fix in self.failed_fixes:
                report_lines.append(
                    f"  - {fix.get('type')} at {fix.get('location')}: {fix.get('reason')}"
                )

        report_lines.append("=" * 60)

        return "\n".join(report_lines)
