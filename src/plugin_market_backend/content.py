"""Helpers for plugin market rich content and uploaded assets."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import secrets
import zipfile
from pathlib import Path

import bleach
import yaml
from markdown import markdown
from PIL import Image, ImageOps

from plugin_market_backend.errors import ApiError

PLUGIN_MEDIA_DIR = Path("data") / "plugin_media"
PLUGIN_ICON_DIR = PLUGIN_MEDIA_DIR / "icons"
PROFILE_BG_DIR = PLUGIN_MEDIA_DIR / "profile_backgrounds"

# Upload limits (must match documented behaviour for the frontend).
MAX_ICON_BYTES = 2 * 1024 * 1024  # 2 MiB
MAX_BACKGROUND_BYTES = 5 * 1024 * 1024  # 5 MiB
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}

ALLOWED_MARKDOWN_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
    {
        "p",
        "pre",
        "code",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "br",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "blockquote",
    }
)
ALLOWED_MARKDOWN_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "code": ["class"],
    "th": ["align"],
    "td": ["align"],
}


def ensure_plugin_media_dirs() -> None:
    """Ensure directories for stored plugin media exist."""

    PLUGIN_ICON_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_BG_DIR.mkdir(parents=True, exist_ok=True)


def store_plugin_icon(plugin_id: str, icon_png_base64: str) -> str:
    """Normalize and persist a plugin icon, returning its public URL."""

    ensure_plugin_media_dirs()
    try:
        raw = base64.b64decode(icon_png_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError(422, "INVALID_ICON", "Plugin icon must be valid base64-encoded PNG data.") from exc

    try:
        with Image.open(io.BytesIO(raw)) as image:
            if (image.format or "").upper() != "PNG":
                raise ApiError(422, "INVALID_ICON", "Plugin icon must be a PNG image.")
            working = ImageOps.contain(image.convert("RGBA"), (512, 512), method=Image.Resampling.LANCZOS)
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(422, "INVALID_ICON", "Plugin icon could not be decoded as a PNG image.") from exc

    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    offset = ((512 - working.width) // 2, (512 - working.height) // 2)
    canvas.paste(working, offset, working)
    normalized = canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)

    icon_path = plugin_icon_path(plugin_id)
    normalized.save(icon_path, format="PNG", optimize=True)
    return plugin_icon_url(plugin_id)


def delete_plugin_icon(plugin_id: str) -> None:
    """Delete a stored plugin icon when the plugin clears it."""

    icon_path = plugin_icon_path(plugin_id)
    if icon_path.exists():
        icon_path.unlink()


def plugin_icon_path(plugin_id: str) -> Path:
    """Return the icon path for a plugin."""

    return PLUGIN_ICON_DIR / f"{plugin_id}.png"


def plugin_icon_url(plugin_id: str) -> str:
    """Return the public URL for a stored plugin icon."""

    return f"/plugin-media/icons/{plugin_id}.png"


def normalize_readme_markdown(value: str | None) -> str | None:
    """Normalize README markdown before persistence."""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def render_readme_html(value: str | None) -> str | None:
    """Render README markdown into sanitized HTML."""

    normalized = normalize_readme_markdown(value)
    if normalized is None:
        return None
    rendered = markdown(
        normalized,
        extensions=["extra", "fenced_code", "tables", "sane_lists", "nl2br"],
        output_format="html5",
    )
    cleaned = bleach.clean(rendered, tags=ALLOWED_MARKDOWN_TAGS, attributes=ALLOWED_MARKDOWN_ATTRIBUTES, strip=True)
    return bleach.linkify(cleaned)



# ---------------------------------------------------------------------------
# Multipart image uploads (icon / profile background)
# ---------------------------------------------------------------------------

def store_plugin_icon_from_bytes(plugin_id: str, raw_bytes: bytes) -> str:
    """Persist a plugin icon from raw uploaded bytes.

    Accepts PNG / JPEG / WEBP / GIF, normalizes everything to a 512×512 PNG
    (transparent canvas, contained), and returns the public URL.
    """

    ensure_plugin_media_dirs()
    if len(raw_bytes) == 0:
        raise ApiError(422, "INVALID_ICON", "Plugin icon file is empty.")
    if len(raw_bytes) > MAX_ICON_BYTES:
        raise ApiError(
            422,
            "INVALID_ICON",
            f"Plugin icon must not exceed {MAX_ICON_BYTES // 1024 // 1024} MiB.",
            {"max_bytes": MAX_ICON_BYTES, "received": len(raw_bytes)},
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            fmt = (image.format or "").upper()
            if fmt not in ALLOWED_IMAGE_FORMATS:
                raise ApiError(
                    422,
                    "INVALID_ICON",
                    "Unsupported image format. Allowed: PNG / JPEG / WEBP / GIF.",
                    {"format": fmt},
                )
            working = ImageOps.contain(
                image.convert("RGBA"), (512, 512), method=Image.Resampling.LANCZOS
            )
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(422, "INVALID_ICON", "Plugin icon could not be decoded as an image.") from exc

    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    offset = ((512 - working.width) // 2, (512 - working.height) // 2)
    canvas.paste(working, offset, working)
    normalized = canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)

    icon_path = plugin_icon_path(plugin_id)
    normalized.save(icon_path, format="PNG", optimize=True)
    return plugin_icon_url(plugin_id)


def store_profile_background(author_id: str, raw_bytes: bytes) -> str:
    """Persist a personal-space background image from uploaded bytes.

    Accepts PNG / JPEG / WEBP, resizes to fit within 1920×1080 (covers most
    desktop hero positions while keeping bytes reasonable), saves as JPEG
    (quality 86) for compactness, returns a public URL.
    """

    ensure_plugin_media_dirs()
    if len(raw_bytes) == 0:
        raise ApiError(422, "PROFILE_BACKGROUND_EMPTY", "Background image file is empty.")
    if len(raw_bytes) > MAX_BACKGROUND_BYTES:
        raise ApiError(
            422,
            "PROFILE_BACKGROUND_TOO_LARGE",
            f"Background image must not exceed {MAX_BACKGROUND_BYTES // 1024 // 1024} MiB.",
            {"max_bytes": MAX_BACKGROUND_BYTES, "received": len(raw_bytes)},
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            fmt = (image.format or "").upper()
            if fmt not in {"PNG", "JPEG", "WEBP"}:
                raise ApiError(
                    422,
                    "PROFILE_BACKGROUND_INVALID_FORMAT",
                    "Background image format must be PNG / JPEG / WEBP.",
                    {"format": fmt},
                )
            rgb = image.convert("RGB")
            working = ImageOps.contain(rgb, (1920, 1080), method=Image.Resampling.LANCZOS)
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(
            422,
            "PROFILE_BACKGROUND_INVALID",
            "Background image could not be decoded.",
        ) from exc

    safe_id = "".join(ch for ch in author_id if ch.isalnum() or ch in {"-", "_"}).strip("-_") or "anon"
    suffix = secrets.token_hex(4)
    filename = f"{safe_id}-{suffix}.jpg"
    target = PROFILE_BG_DIR / filename
    working.save(target, format="JPEG", quality=86, optimize=True)
    return f"/plugin-media/profile_backgrounds/{filename}"


def delete_profile_background_url(url: str | None) -> None:
    """Best-effort delete a previously stored profile background asset."""

    if not url or not url.startswith("/plugin-media/profile_backgrounds/"):
        return
    name = url.split("/")[-1]
    if not name:
        return
    path = PROFILE_BG_DIR / name
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Skill package storage
# ---------------------------------------------------------------------------

SKILL_PACKAGES_DIR = Path("data") / "skill_packages"
MAX_SKILL_PACKAGE_BYTES = 10 * 1024 * 1024  # 10 MiB


def ensure_skill_dirs() -> None:
    """Ensure the skill package storage directory exists."""

    SKILL_PACKAGES_DIR.mkdir(parents=True, exist_ok=True)


def store_skill_package(skill_id: str, version: str, zip_bytes: bytes) -> str:
    """Persist a skill zip package and return its storage path.

    The package is stored as ``data/skill_packages/{skill_id}/{version}.zip``.
    """

    ensure_skill_dirs()
    skill_dir = SKILL_PACKAGES_DIR / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    package_path = skill_dir / f"{version}.zip"
    package_path.write_bytes(zip_bytes)
    return str(package_path)


def extract_and_validate_skill(zip_bytes: bytes) -> tuple[str, str, str]:
    """Validate a skill zip package and extract metadata.

    Returns ``(name, description, readme_text)``.

    The zip must:
    * Be a valid zip archive.
    * Not exceed ``MAX_SKILL_PACKAGE_BYTES``.
    * Contain a ``SKILL.md`` file at the root.
    * The ``SKILL.md`` must have YAML front matter with at least ``name``.

    Raises ``ApiError(422, ...)`` on any validation failure.
    """

    if len(zip_bytes) == 0:
        raise ApiError(422, "SKILL_PACKAGE_EMPTY", "Skill package is empty.")
    if len(zip_bytes) > MAX_SKILL_PACKAGE_BYTES:
        raise ApiError(
            422,
            "SKILL_PACKAGE_TOO_LARGE",
            f"Skill package must not exceed {MAX_SKILL_PACKAGE_BYTES // 1024 // 1024} MiB.",
            {"max_bytes": MAX_SKILL_PACKAGE_BYTES, "received": len(zip_bytes)},
        )

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # Security: reject paths that escape the archive root
            for name in zf.namelist():
                if name.startswith("/") or ".." in name.split("/"):
                    raise ApiError(
                        422,
                        "SKILL_PACKAGE_INSECURE_PATH",
                        f"Skill package contains an insecure path: {name!r}.",
                    )

            # Locate SKILL.md at the root (allow one level of nesting via a
            # top-level directory, common when zipping a folder)
            skill_md_candidates = [
                n for n in zf.namelist()
                if n == "SKILL.md" or n.endswith("/SKILL.md") and n.count("/") == 1
            ]
            if not skill_md_candidates:
                raise ApiError(
                    422,
                    "SKILL_PACKAGE_NO_SKILL_MD",
                    "Skill package must contain a SKILL.md file (exact uppercase) at the zip root.",
                )
            # Prefer an exact root match; otherwise use the first single-nesting candidate
            skill_md_name = "SKILL.md" if "SKILL.md" in skill_md_candidates else skill_md_candidates[0]
            readme_text = zf.read(skill_md_name).decode("utf-8")

            # Parse YAML front matter
            front_matter: dict[str, str] = {}
            body_lines: list[str] = []
            if readme_text.startswith("---"):
                parts = readme_text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        front_matter = yaml.safe_load(parts[1]) or {}
                    except yaml.YAMLError as exc:
                        raise ApiError(
                            422,
                            "SKILL_PACKAGE_INVALID_FRONT_MATTER",
                            "SKILL.md 的 YAML 头部格式错误，请检查 `---` 包裹的 YAML 语法",
                        ) from exc
                    body_lines = parts[2].splitlines()
            else:
                body_lines = readme_text.splitlines()

            name = front_matter.get("name", "").strip()
            if not name:
                raise ApiError(
                    422,
                    "SKILL_PACKAGE_MISSING_NAME",
                    "SKILL.md 的 YAML 头部必须包含非空的 name 字段，例如: `name: My Skill`",
                )
            description = front_matter.get("description", "").strip()
            body = "\n".join(body_lines).strip()

            return name, description, body

    except ApiError:
        raise
    except zipfile.BadZipFile as exc:
        raise ApiError(
            422,
            "SKILL_PACKAGE_NOT_ZIP",
            "Skill package is not a valid zip archive.",
        ) from exc
    except UnicodeDecodeError as exc:
        raise ApiError(
            422,
            "SKILL_PACKAGE_ENCODING",
            "SKILL.md must be a UTF-8 encoded text file.",
        ) from exc
