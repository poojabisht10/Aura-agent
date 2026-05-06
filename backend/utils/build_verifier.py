"""Build verification utilities for generated projects."""
import asyncio
import re
from pathlib import Path
from typing import Dict, Any, Optional

from backend.utils import get_npm_command, get_npx_command


async def verify_build(project_path: Path, timeout: int = 120) -> Dict[str, Any]:
    """
    Run build and verify no errors.
    
    Args:
        project_path: Path to the project directory
        timeout: Build timeout in seconds
        
    Returns:
        Dictionary with:
        - success: bool
        - errors: list of build errors
        - warnings: list of build warnings
        - bundle_size: size information if build succeeded
        - duration: build duration in seconds
    """
    print(f"[Build Verifier] Building project at {project_path}")
    
    import time
    start_time = time.time()
    
    try:
        # Run npm run build
        process = await asyncio.create_subprocess_exec(
            get_npm_command(), "run", "build",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()  # reap the process
            raise
        
        duration = round(time.time() - start_time, 2)
        output = stdout.decode("utf-8") + "\n" + stderr.decode("utf-8")
        
        # Parse build errors
        errors = []
        warnings = []
        
        # TypeScript errors
        ts_error_pattern = re.compile(r"error TS\d+: (.+)")
        for match in ts_error_pattern.finditer(output):
            errors.append({
                "type": "typescript",
                "message": match.group(1),
            })
        
        # Vite/Rollup errors
        if "Error:" in output or "error:" in output.lower():
            error_lines = [line for line in output.split("\n") if "error" in line.lower()]
            for line in error_lines[:10]:  # Limit to 10 errors
                if line.strip() and "Error:" in line:
                    errors.append({
                        "type": "build",
                        "message": line.strip(),
                    })
        
        # Warnings
        warning_pattern = re.compile(r"warning[:\s]+(.+)", re.IGNORECASE)
        for match in warning_pattern.finditer(output):
            warnings.append({
                "type": "warning",
                "message": match.group(1).strip(),
            })
        
        success = process.returncode == 0
        
        # Get bundle size if build succeeded
        bundle_size = None
        if success:
            dist_path = project_path / "dist"
            if dist_path.exists():
                total_size = sum(
                    f.stat().st_size 
                    for f in dist_path.rglob("*") 
                    if f.is_file()
                )
                bundle_size = {
                    "total_bytes": total_size,
                    "total_kb": round(total_size / 1024, 2),
                    "total_mb": round(total_size / (1024 * 1024), 2),
                }
        
        print(f"[Build Verifier] Build {'succeeded' if success else 'failed'} in {duration}s")
        if errors:
            for e in errors[:5]:
                print(f"[Build Verifier]   ✗ {e.get('type', 'error')}: {e.get('message', '')}")
        
        return {
            "success": success,
            "errors": errors,
            "warnings": warnings,
            "bundle_size": bundle_size,
            "duration": duration,
            "exit_code": process.returncode,
        }
    
    except asyncio.TimeoutError:
        print(f"[Build Verifier] Build timed out after {timeout}s")
        return {
            "success": False,
            "errors": [{"type": "timeout", "message": f"Build timed out after {timeout}s"}],
            "warnings": [],
            "bundle_size": None,
            "duration": timeout,
        }
    
    except Exception as e:
        print(f"[Build Verifier] Error running build: {e}")
        return {
            "success": False,
            "errors": [{"type": "exception", "message": str(e)}],
            "warnings": [],
            "bundle_size": None,
            "duration": round(time.time() - start_time, 2),
        }


async def run_typecheck(project_path: Path) -> Dict[str, Any]:
    """
    Run TypeScript type checking without emitting files.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Dictionary with type check results
    """
    print(f"[Build Verifier] Type checking project at {project_path}")
    
    try:
        process = await asyncio.create_subprocess_exec(
            get_npx_command(), "tsc", "--noEmit",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        output = stdout.decode("utf-8") + stderr.decode("utf-8")
        
        # Parse TypeScript errors
        errors = []
        error_pattern = re.compile(r"(.+)\((\d+),(\d+)\): error (TS\d+): (.+)")
        
        for match in error_pattern.finditer(output):
            errors.append({
                "file": match.group(1),
                "line": int(match.group(2)),
                "column": int(match.group(3)),
                "code": match.group(4),
                "message": match.group(5),
            })
        
        print(f"[Build Verifier] Type check found {len(errors)} errors")
        
        return {
            "success": process.returncode == 0,
            "errors": errors,
            "error_count": len(errors),
        }
    
    except Exception as e:
        print(f"[Build Verifier] Error running type check: {e}")
        return {
            "success": False,
            "errors": [{"message": str(e)}],
            "error_count": 1,
        }


async def install_dependencies(project_path: Path, timeout: int = 180) -> Dict[str, Any]:
    """
    Install project dependencies using npm.
    
    Args:
        project_path: Path to the project directory
        timeout: Installation timeout in seconds
        
    Returns:
        Dictionary with installation results
    """
    print(f"[Build Verifier] Installing dependencies at {project_path}")
    
    import time
    start_time = time.time()
    
    try:
        process = await asyncio.create_subprocess_exec(
            get_npm_command(), "install",
            cwd=str(project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()  # reap the process
            raise
        
        duration = round(time.time() - start_time, 2)
        
        print(f"[Build Verifier] Dependencies installed in {duration}s")
        
        return {
            "success": process.returncode == 0,
            "duration": duration,
            "output": stdout.decode("utf-8"),
        }
    
    except asyncio.TimeoutError:
        print(f"[Build Verifier] Installation timed out after {timeout}s")
        return {
            "success": False,
            "duration": timeout,
            "error": f"Installation timed out after {timeout}s",
        }
    
    except Exception as e:
        print(f"[Build Verifier] Error installing dependencies: {e}")
        return {
            "success": False,
            "duration": round(time.time() - start_time, 2),
            "error": str(e),
        }


async def full_verification(project_path: Path) -> Dict[str, Any]:
    """
    Run full verification pipeline: install, typecheck, build.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        Combined results from all verification steps
    """
    print(f"[Build Verifier] Running full verification on {project_path}")
    
    results = {
        "install": None,
        "typecheck": None,
        "build": None,
        "overall_success": True,
    }
    
    # Check if node_modules exists
    node_modules_path = project_path / "node_modules"
    if not node_modules_path.exists():
        results["install"] = await install_dependencies(project_path)
        if not results["install"].get("success"):
            results["overall_success"] = False
            return results
    else:
        results["install"] = {"success": True, "skipped": True}
    
    # Run type check
    results["typecheck"] = await run_typecheck(project_path)
    
    # Run build
    results["build"] = await verify_build(project_path)
    if not results["build"].get("success"):
        results["overall_success"] = False
    
    print(f"[Build Verifier] Full verification {'passed' if results['overall_success'] else 'failed'}")
    
    return results
