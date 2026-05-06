"""Image optimizer for generated projects.

Scans project images and compresses files that exceed a size threshold,
reducing deployment payload size and improving page load times.
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Supported image extensions (lowercase)
_JPEG_EXTS = {".jpg", ".jpeg"}
_PNG_EXTS = {".png"}
_SKIP_EXTS = {".svg", ".ico"}
_IMAGE_EXTS = _JPEG_EXTS | _PNG_EXTS | {".webp", ".gif"} | _SKIP_EXTS


async def optimize_project_images(
    project_path: Path, max_size_kb: int = 500
) -> dict:
    """Optimize images in a project's public/images directory.

    For files exceeding *max_size_kb*:
    - JPEG: progressively reduce quality (85 -> 70 -> 50) until under limit.
    - PNG: attempt WebP conversion; if smaller, replace with WebP; otherwise
      compress the PNG with optimize=True and reduced colors.
    - SVG / ICO: skipped (already small or not bitmap).

    Args:
        project_path: Root path of the generated project.
        max_size_kb: Maximum allowed file size in kilobytes.

    Returns:
        Report dict with keys: files_processed, files_skipped,
        space_saved_kb, details.
    """
    images_dir = project_path / "public" / "images"

    report: dict = {
        "files_processed": 0,
        "files_skipped": 0,
        "space_saved_kb": 0.0,
        "details": [],
    }

    if not images_dir.exists():
        logger.debug("No images directory at %s, nothing to optimize.", images_dir)
        return report

    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow not installed -- skipping image optimization.")
        return report

    image_files: List[Path] = [
        f for f in images_dir.rglob("*") if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
    ]

    for img_path in image_files:
        ext = img_path.suffix.lower()
        original_kb = img_path.stat().st_size / 1024

        # Skip small files and non-bitmap formats
        if ext in _SKIP_EXTS or original_kb <= max_size_kb:
            report["files_skipped"] += 1
            continue

        try:
            saved_kb = 0.0
            action = "skipped"

            if ext in _JPEG_EXTS:
                saved_kb, action = _optimize_jpeg(img_path, max_size_kb, Image)
            elif ext in _PNG_EXTS:
                saved_kb, action = _optimize_png(img_path, max_size_kb, Image)
            elif ext == ".webp":
                saved_kb, action = _optimize_webp(img_path, max_size_kb, Image)
            else:
                report["files_skipped"] += 1
                continue

            # If PNG was converted to WebP, original is deleted; calculate from saved_kb
            if img_path.exists():
                new_kb = img_path.stat().st_size / 1024
            else:
                new_kb = original_kb - saved_kb
            report["files_processed"] += 1
            report["space_saved_kb"] += saved_kb
            report["details"].append({
                "file": str(img_path.relative_to(project_path)),
                "original_kb": round(original_kb, 1),
                "new_kb": round(new_kb, 1),
                "action": action,
            })

        except Exception as exc:
            logger.warning("Failed to optimize %s: %s", img_path.name, exc)
            report["files_skipped"] += 1

    report["space_saved_kb"] = round(report["space_saved_kb"], 1)

    if report["files_processed"] > 0:
        logger.info(
            "Image optimization: %d files processed, %.1f KB saved.",
            report["files_processed"],
            report["space_saved_kb"],
        )

    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_save(img, img_path: Path, fmt: str, **kwargs):
    """Save image to a temp file first, then replace the original.

    This avoids corrupting the original file if Pillow fails mid-write.
    Also handles Windows file locking by loading pixels before saving.
    """
    # Force full pixel load to release the source file handle (Windows fix)
    img.load()

    # Convert RGBA to RGB for JPEG (JPEG doesn't support alpha)
    if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=img_path.suffix, dir=img_path.parent)
    tmp_path = Path(tmp_path_str)
    try:
        import os
        os.close(tmp_fd)
        img.save(tmp_path, fmt, **kwargs)
        shutil.move(str(tmp_path), str(img_path))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _optimize_jpeg(img_path: Path, max_size_kb: int, Image) -> tuple:
    """Progressively reduce JPEG quality until under the size limit."""
    original_kb = img_path.stat().st_size / 1024
    qualities = [85, 70, 50]

    for quality in qualities:
        try:
            img = Image.open(img_path)
            _safe_save(img, img_path, "JPEG", quality=quality, optimize=True)
            new_kb = img_path.stat().st_size / 1024
            if new_kb <= max_size_kb:
                return (original_kb - new_kb, f"jpeg quality={quality}")
        except Exception:
            break

    new_kb = img_path.stat().st_size / 1024
    return (original_kb - new_kb, "jpeg quality=50 (still over limit)")


def _optimize_png(img_path: Path, max_size_kb: int, Image) -> tuple:
    """Try converting PNG to WebP; fallback to PNG compression."""
    original_kb = img_path.stat().st_size / 1024

    # Try WebP conversion first
    webp_path = img_path.with_suffix(".webp")
    try:
        img = Image.open(img_path)
        img.load()  # Release file handle
        img.save(webp_path, "WEBP", quality=80, method=4)
        webp_kb = webp_path.stat().st_size / 1024

        if webp_kb < original_kb:
            # WebP is smaller -- replace original
            img_path.unlink()
            saved = original_kb - webp_kb
            return (saved, f"converted to webp ({webp_path.name})")
        else:
            # WebP not smaller -- remove it and compress PNG instead
            webp_path.unlink()
    except Exception:
        if webp_path.exists():
            webp_path.unlink()

    # Fallback: compress PNG
    try:
        img = Image.open(img_path)
        _safe_save(img, img_path, "PNG", optimize=True)
        new_kb = img_path.stat().st_size / 1024
        return (original_kb - new_kb, "png optimize")
    except Exception:
        return (0.0, "png unchanged")


def _optimize_webp(img_path: Path, max_size_kb: int, Image) -> tuple:
    """Reduce WebP quality until under the size limit."""
    original_kb = img_path.stat().st_size / 1024
    qualities = [80, 60, 40]

    for quality in qualities:
        try:
            img = Image.open(img_path)
            _safe_save(img, img_path, "WEBP", quality=quality, method=4)
            new_kb = img_path.stat().st_size / 1024
            if new_kb <= max_size_kb:
                return (original_kb - new_kb, f"webp quality={quality}")
        except Exception:
            break

    new_kb = img_path.stat().st_size / 1024
    return (original_kb - new_kb, "webp compressed (still over limit)")
