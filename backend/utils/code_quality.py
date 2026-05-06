"""Code quality utilities for ESLint, Prettier, and optimization checks."""
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

from backend.utils import get_npm_command, get_npx_command


async def run_eslint(project_path: Path) -> Dict[str, Any]:
    """
    Run ESLint on the generated project and return results.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with:
        - success: bool
        - errors: list of error objects
        - warnings: list of warning objects
        - fixable_count: number of fixable issues
        - error_count: total errors
        - warning_count: total warnings
    """
    print(f"[ESLint] Running on {project_path}")
    
    try:
        # Run ESLint with JSON output
        process = await asyncio.create_subprocess_exec(
            get_npm_command(), "run", "lint", "--", "--format", "json",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        # ESLint returns exit code 1 if there are errors, but we still want to parse output
        output = stdout.decode("utf-8")
        
        # Try to parse JSON output
        try:
            results = json.loads(output) if output.strip() else []
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract error count from text output
            error_match = re.search(r'(\d+) errors?', output)
            warning_match = re.search(r'(\d+) warnings?', output)
            error_count = int(error_match.group(1)) if error_match else 0
            warning_count = int(warning_match.group(1)) if warning_match else 0

            return {
                "success": error_count == 0,  # success if no actual errors found
                "errors": [],
                "warnings": [],
                "fixable_count": 0,
                "error_count": error_count,
                "warning_count": warning_count,
                "raw_output": output,
            }
        
        # Process ESLint JSON results
        errors = []
        warnings = []
        fixable_count = 0
        
        for file_result in results:
            file_path = file_result.get("filePath", "")
            for message in file_result.get("messages", []):
                issue = {
                    "file": file_path,
                    "line": message.get("line", 0),
                    "column": message.get("column", 0),
                    "rule": message.get("ruleId", ""),
                    "message": message.get("message", ""),
                    "severity": message.get("severity", 0),
                    "fix": message.get("fix") is not None,
                }
                
                if message.get("fix"):
                    fixable_count += 1
                
                if message.get("severity") == 2:
                    errors.append(issue)
                else:
                    warnings.append(issue)
        
        print(f"[ESLint] Found {len(errors)} errors, {len(warnings)} warnings ({fixable_count} fixable)")
        
        return {
            "success": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "fixable_count": fixable_count,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }
    
    except Exception as e:
        print(f"[ESLint] Error running ESLint: {e}")
        return {
            "success": False,
            "errors": [{"message": str(e)}],
            "warnings": [],
            "fixable_count": 0,
            "error_count": 1,
            "warning_count": 0,
        }


async def run_eslint_fix(project_path: Path) -> Dict[str, Any]:
    """
    Run ESLint with --fix to auto-fix issues.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with success status and fixed count
    """
    print(f"[ESLint] Running auto-fix on {project_path}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            get_npm_command(), "run", "lint", "--", "--fix",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        print(f"[ESLint] Auto-fix completed with exit code {process.returncode}")
        
        return {
            "success": process.returncode == 0,
            "output": stdout.decode("utf-8"),
        }
    
    except Exception as e:
        print(f"[ESLint] Error running auto-fix: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def run_prettier(project_path: Path) -> Dict[str, Any]:
    """
    Run Prettier to check code formatting.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with success status and unformatted files
    """
    print(f"[Prettier] Checking formatting in {project_path}")
    
    try:
        # Check if prettier is installed
        package_json_path = project_path / "package.json"
        if package_json_path.exists():
            with open(package_json_path) as f:
                package_json = json.load(f)
            
            has_prettier = "prettier" in package_json.get("devDependencies", {})
            if not has_prettier:
                return {
                    "success": True,
                    "skipped": True,
                    "message": "Prettier not installed in project",
                }
        
        # Run Prettier check
        process = await asyncio.create_subprocess_exec(
            get_npx_command(), "prettier", "--check", "src/**/*.ts", "src/**/*.tsx", "src/**/*.css",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode("utf-8") + stderr.decode("utf-8")
        
        # Parse unformatted files (filter out Prettier summary/status lines)
        skip_phrases = ["Checking", "All matched files", "error", "warn"]
        unformatted = []
        for line in output.split("\n"):
            stripped = line.strip()
            if stripped and not any(stripped.startswith(p) or stripped.lower().startswith(p.lower()) for p in skip_phrases):
                unformatted.append(stripped)
        
        print(f"[Prettier] {len(unformatted)} files need formatting")
        
        return {
            "success": process.returncode == 0,
            "unformatted_files": unformatted,
            "count": len(unformatted),
        }
    
    except Exception as e:
        print(f"[Prettier] Error checking formatting: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def run_prettier_format(project_path: Path) -> Dict[str, Any]:
    """
    Run Prettier to format all files.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with success status
    """
    print(f"[Prettier] Formatting files in {project_path}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            get_npx_command(), "prettier", "--write", "src/**/*.ts", "src/**/*.tsx", "src/**/*.css",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        print(f"[Prettier] Formatting completed with exit code {process.returncode}")
        
        return {
            "success": process.returncode == 0,
            "output": stdout.decode("utf-8"),
        }
    
    except Exception as e:
        print(f"[Prettier] Error formatting: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def check_unused_imports(project_path: Path) -> Dict[str, Any]:
    """
    Check for unused imports using TypeScript compiler.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with unused imports by file
    """
    print(f"[Optimization] Checking unused imports in {project_path}")
    
    try:
        # Run TypeScript compiler with noEmit to check for errors
        process = await asyncio.create_subprocess_exec(
            get_npx_command(), "tsc", "--noEmit",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode("utf-8") + stderr.decode("utf-8")
        
        # Parse TypeScript errors for unused variables/imports
        unused_imports = []
        unused_pattern = re.compile(r"'(.+)' is declared but (its value is )?never (used|read)")
        
        for line in output.split("\n"):
            match = unused_pattern.search(line)
            if match:
                unused_imports.append({
                    "name": match.group(1),
                    "line": line,
                })
        
        print(f"[Optimization] Found {len(unused_imports)} unused imports/variables")
        
        return {
            "success": True,
            "unused_imports": unused_imports,
            "count": len(unused_imports),
        }
    
    except Exception as e:
        print(f"[Optimization] Error checking unused imports: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def analyze_bundle_size(project_path: Path) -> Dict[str, Any]:
    """
    Analyze bundle size after building the project.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with bundle size information
    """
    print(f"[Optimization] Analyzing bundle size for {project_path}")
    
    try:
        dist_path = project_path / "dist"
        
        if not dist_path.exists():
            return {
                "success": False,
                "message": "dist folder not found. Run build first.",
            }
        
        # Calculate total size
        total_size = 0
        files = []
        
        for file_path in dist_path.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                total_size += size
                files.append({
                    "path": str(file_path.relative_to(dist_path)),
                    "size": size,
                    "size_kb": round(size / 1024, 2),
                })
        
        # Sort by size descending
        files.sort(key=lambda x: x["size"], reverse=True)
        
        # Find JS and CSS bundles
        js_bundles = [f for f in files if f["path"].endswith(".js")]
        css_bundles = [f for f in files if f["path"].endswith(".css")]
        
        print(f"[Optimization] Total bundle size: {round(total_size / 1024, 2)} KB")
        
        return {
            "success": True,
            "total_size": total_size,
            "total_size_kb": round(total_size / 1024, 2),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "js_size_kb": sum(f["size_kb"] for f in js_bundles),
            "css_size_kb": sum(f["size_kb"] for f in css_bundles),
            "largest_files": files[:10],
        }
    
    except Exception as e:
        print(f"[Optimization] Error analyzing bundle size: {e}")
        return {
            "success": False,
            "error": str(e),
        }


async def run_all_quality_checks(project_path: Path, auto_fix: bool = True) -> Dict[str, Any]:
    """
    Run all code quality checks on a project.
    
    Args:
        project_path: Path to the project directory
        auto_fix: Whether to auto-fix issues where possible
        
    Returns:
        Combined results from all checks
    """
    print(f"[Code Quality] Running all checks on {project_path}")
    
    results = {
        "eslint": None,
        "prettier": None,
        "unused_imports": None,
        "bundle_size": None,
        "overall_success": True,
    }
    
    # Run ESLint
    results["eslint"] = await run_eslint(project_path)
    if auto_fix and results["eslint"].get("fixable_count", 0) > 0:
        await run_eslint_fix(project_path)
        results["eslint"] = await run_eslint(project_path)

    # Always log ESLint results
    errors_count = results["eslint"].get("error_count", 0)
    warnings_count = results["eslint"].get("warning_count", 0)
    print(f"[Quality] ESLint: {errors_count} errors, {warnings_count} warnings")
    if errors_count > 0:
        for e in results["eslint"].get("errors", [])[:5]:
            file_short = str(e.get('file', '')).split('src/')[-1] if 'src/' in str(e.get('file', '')) else e.get('file', '')
            print(f"[Quality]   ✗ {file_short}:{e.get('line', '')} — {e.get('rule', '')} — {e.get('message', '')}")
    if results["eslint"].get("raw_output") and not results["eslint"].get("errors"):
        # JSON parse failed — show raw output snippet
        raw = results["eslint"].get("raw_output", "")[:300]
        print(f"[Quality] ESLint raw output: {raw}")

    if not results["eslint"].get("success"):
        results["overall_success"] = False

    # Run Prettier
    results["prettier"] = await run_prettier(project_path)
    if auto_fix and results["prettier"].get("count", 0) > 0:
        await run_prettier_format(project_path)
        results["prettier"] = await run_prettier(project_path)
        fixed = results["prettier"].get("count", 0)
        if fixed > 0:
            files = results["prettier"].get("unformatted_files", [])
            print(f"[Quality] Prettier: {fixed} file(s) need formatting: {', '.join(files[:3])}")
    if not results["prettier"].get("success"):
        results["overall_success"] = False

    # Check unused imports
    results["unused_imports"] = await check_unused_imports(project_path)
    
    # Analyze bundle size if build exists
    results["bundle_size"] = await analyze_bundle_size(project_path)
    
    if not results["overall_success"]:
        reasons = []
        if not results["eslint"].get("success"): reasons.append("ESLint errors")
        if not results["prettier"].get("success"): reasons.append("Prettier failures")
        if reasons:
            print(f"[Quality] overall_success=False — {', '.join(reasons)}")
    print(f"[Code Quality] Overall success: {results['overall_success']}")

    return results
