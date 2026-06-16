"""Helpers for plugin market rich content and uploaded assets."""

from __future__ import annotations

import base64
import binascii
import io
import json
import secrets
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import bleach
import yaml
from markdown import markdown
from PIL import Image, ImageOps

from plugin_market_backend.config import get_settings
from plugin_market_backend.errors import ApiError

_LEGACY_DATA_PREFIX = "data"
SKILL_MANIFEST_SCHEMA_VERSION = 1

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


@dataclass(slots=True)
class SkillArchiveMetadata:
    """Parsed metadata extracted from an uploaded skill zip package."""

    name: str
    description: str
    readme_text: str
    front_matter: dict[str, Any]


def ensure_plugin_media_dirs() -> None:
    """Ensure directories for stored plugin media exist."""

    plugin_icon_dir().mkdir(parents=True, exist_ok=True)
    profile_background_dir().mkdir(parents=True, exist_ok=True)


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

    return plugin_icon_dir() / f"{plugin_id}.png"


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
    target = profile_background_dir() / filename
    working.save(target, format="JPEG", quality=86, optimize=True)
    return f"/plugin-media/profile_backgrounds/{filename}"


def delete_profile_background_url(url: str | None) -> None:
    """Best-effort delete a previously stored profile background asset."""

    if not url or not url.startswith("/plugin-media/profile_backgrounds/"):
        return
    name = url.split("/")[-1]
    if not name:
        return
    path = profile_background_dir() / name
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Skill package storage
# ---------------------------------------------------------------------------

MAX_SKILL_PACKAGE_BYTES = 10 * 1024 * 1024  # 10 MiB


def storage_root_dir() -> Path:
    """Return the configured storage root directory."""

    return get_settings().storage_path


def plugin_media_dir() -> Path:
    """Return the root directory for uploaded public media."""

    return storage_root_dir() / "plugin_media"


def plugin_icon_dir() -> Path:
    """Return the directory for normalized plugin icons."""

    return plugin_media_dir() / "icons"


def profile_background_dir() -> Path:
    """Return the directory for uploaded profile backgrounds."""

    return plugin_media_dir() / "profile_backgrounds"


def skill_packages_dir() -> Path:
    """Return the directory for stored skill zip packages."""

    return storage_root_dir() / "skill_packages"


PLUGIN_MEDIA_DIR = plugin_media_dir()


def ensure_skill_dirs() -> None:
    """Ensure the skill package storage directory exists."""

    skill_packages_dir().mkdir(parents=True, exist_ok=True)


def _validate_storage_segment(value: str, *, field_name: str, error_code: str) -> str:
    """Validate a logical identifier that will become one encoded path segment."""

    normalized = value.strip()
    if not normalized:
        raise ApiError(422, error_code, f"{field_name} must not be empty.", {field_name: value})
    if normalized in {".", ".."}:
        raise ApiError(422, error_code, f"{field_name} must not be '.' or '..'.", {field_name: value})
    if "/" in normalized or "\\" in normalized:
        raise ApiError(
            422,
            error_code,
            f"{field_name} must not contain path separators.",
            {field_name: value},
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise ApiError(
            422,
            error_code,
            f"{field_name} must not contain control characters.",
            {field_name: value},
        )
    return normalized


def validate_skill_id(skill_id: str) -> str:
    """Validate and normalize a skill id used in APIs and storage."""

    return _validate_storage_segment(
        skill_id,
        field_name="skill_id",
        error_code="INVALID_SKILL_ID",
    )


def validate_skill_version(version: str) -> str:
    """Validate and normalize a skill version used in APIs and storage."""

    return _validate_storage_segment(
        version,
        field_name="version",
        error_code="INVALID_SKILL_VERSION",
    )


def _encode_storage_segment(value: str) -> str:
    """Encode an arbitrary identifier into a single filesystem-safe segment."""

    return quote(value, safe="")


def _decode_storage_segment(value: str) -> str:
    """Decode one storage path segment back to its logical identifier."""

    return unquote(value)


def _skill_storage_segments(owner_id: str, skill_id: str, version: str) -> tuple[str, str, str]:
    """Return encoded storage path segments for a skill package."""

    normalized_owner = _validate_storage_segment(
        owner_id,
        field_name="owner_id",
        error_code="INVALID_OWNER_ID",
    )
    normalized_skill_id = validate_skill_id(skill_id)
    normalized_version = validate_skill_version(version)
    return (
        _encode_storage_segment(normalized_owner),
        _encode_storage_segment(normalized_skill_id),
        _encode_storage_segment(normalized_version),
    )


def infer_skill_storage_identifiers(stored_path: str) -> tuple[str | None, str | None, str | None]:
    """Infer ``(owner_id, skill_id, version)`` from a stored package path."""

    raw_path = Path(stored_path)
    parts = list(raw_path.parts)
    if parts and parts[0] == _LEGACY_DATA_PREFIX:
        parts = parts[1:]
    if not parts or parts[0] != "skill_packages":
        return None, None, None

    if len(parts) >= 4:
        owner_id = _decode_storage_segment(parts[-3])
        skill_id = _decode_storage_segment(parts[-2])
        version = _decode_storage_segment(Path(parts[-1]).stem)
        return owner_id, skill_id, version

    if len(parts) >= 3:
        skill_id = _decode_storage_segment(parts[-2])
        version = _decode_storage_segment(Path(parts[-1]).stem)
        return None, skill_id, version

    return None, None, None


def skill_package_manifest_path(package_path: Path) -> Path:
    """Return the sidecar manifest path for one stored skill zip package."""

    return package_path.with_suffix(".json")


def iter_skill_package_files() -> list[tuple[str, Path]]:
    """Return all stored skill package files as ``(stored_path, absolute_path)``."""

    root = skill_packages_dir()
    if not root.exists():
        return []

    storage_root = storage_root_dir()
    items: list[tuple[str, Path]] = []
    for package_path in root.rglob("*.zip"):
        items.append((package_path.relative_to(storage_root).as_posix(), package_path))
    items.sort(key=lambda item: item[0])
    return items


def skill_package_storage_path(owner_id: str, skill_id: str, version: str) -> str:
    """Return the relative storage path for one skill package."""

    safe_owner_id, safe_skill_id, safe_version = _skill_storage_segments(owner_id, skill_id, version)
    return Path("skill_packages", safe_owner_id, safe_skill_id, f"{safe_version}.zip").as_posix()


def store_skill_package(owner_id: str, skill_id: str, version: str, zip_bytes: bytes) -> str:
    """Persist a skill zip package and return its storage path.

    The package is stored under the configured storage root as
    ``skill_packages/{owner_id}/{skill_id}/{version}.zip`` using encoded
    path segments, so logical ids may include Chinese characters or uppercase.
    """

    ensure_skill_dirs()
    stored_path = skill_package_storage_path(owner_id, skill_id, version)
    safe_owner_id, safe_skill_id, safe_version = _skill_storage_segments(owner_id, skill_id, version)
    skill_dir = skill_packages_dir() / safe_owner_id / safe_skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)
    package_path = skill_dir / f"{safe_version}.zip"
    package_path.write_bytes(zip_bytes)
    return stored_path


def write_skill_package_manifest(stored_package_path: str, payload: dict[str, Any]) -> None:
    """Persist a JSON sidecar manifest for one stored skill package."""

    package_path = resolve_skill_package_path(stored_package_path)
    manifest_path = skill_package_manifest_path(package_path)
    data = {"schema_version": SKILL_MANIFEST_SCHEMA_VERSION, **payload}
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_skill_package_manifest(stored_package_path: str) -> dict[str, Any] | None:
    """Load the optional JSON sidecar manifest for one stored skill package."""

    manifest_path = skill_package_manifest_path(resolve_skill_package_path(stored_package_path))
    if not manifest_path.exists():
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def resolve_skill_package_path(stored_path: str) -> Path:
    """Resolve a stored skill package path to an absolute filesystem path.

    Supports both the current storage-relative format and legacy values like
    ``data/skill_packages/...`` that were persisted before the storage-root
    normalization.
    """

    raw_path = Path(stored_path)
    if raw_path.is_absolute():
        return raw_path

    storage_root = storage_root_dir()
    candidates: list[Path] = []
    if raw_path.parts and raw_path.parts[0] == _LEGACY_DATA_PREFIX:
        stripped = Path(*raw_path.parts[1:]) if len(raw_path.parts) > 1 else Path()
        if stripped.parts:
            candidates.append((storage_root / stripped).resolve())
        candidates.append((storage_root.parent / raw_path).resolve())
    else:
        candidates.append((storage_root / raw_path).resolve())
    candidates.append((Path.cwd() / raw_path).resolve())

    seen: set[str] = set()
    deduped: list[Path] = []
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)

    for candidate in deduped:
        if candidate.exists():
            return candidate

    return deduped[0]


def inspect_skill_archive(zip_bytes: bytes) -> SkillArchiveMetadata:
    """Validate a skill zip package and return parsed metadata."""

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
            for name in zf.namelist():
                if name.startswith("/") or ".." in name.split("/"):
                    raise ApiError(
                        422,
                        "SKILL_PACKAGE_INSECURE_PATH",
                        f"Skill package contains an insecure path: {name!r}.",
                    )

            skill_md_candidates = [
                name
                for name in zf.namelist()
                if name == "SKILL.md" or name.endswith("/SKILL.md") and name.count("/") == 1
            ]
            if not skill_md_candidates:
                raise ApiError(
                    422,
                    "SKILL_PACKAGE_NO_SKILL_MD",
                    "Skill package must contain a SKILL.md file (exact uppercase) at the zip root.",
                )

            skill_md_name = "SKILL.md" if "SKILL.md" in skill_md_candidates else skill_md_candidates[0]
            readme_text = zf.read(skill_md_name).decode("utf-8")

            front_matter: dict[str, Any] = {}
            body_lines: list[str] = []
            if readme_text.startswith("---"):
                parts = readme_text.split("---", 2)
                if len(parts) >= 3:
                    try:
                        parsed_front_matter = yaml.safe_load(parts[1]) or {}
                    except yaml.YAMLError as exc:
                        raise ApiError(
                            422,
                            "SKILL_PACKAGE_INVALID_FRONT_MATTER",
                            "SKILL.md 的 YAML 头部格式错误，请检查 `---` 包裹的 YAML 语法",
                        ) from exc
                    if not isinstance(parsed_front_matter, dict):
                        raise ApiError(
                            422,
                            "SKILL_PACKAGE_INVALID_FRONT_MATTER",
                            "SKILL.md 的 YAML 头部必须是键值对对象。",
                        )
                    front_matter = parsed_front_matter
                    body_lines = parts[2].splitlines()
            else:
                body_lines = readme_text.splitlines()

            name = str(front_matter.get("name", "")).strip()
            if not name:
                raise ApiError(
                    422,
                    "SKILL_PACKAGE_MISSING_NAME",
                    "SKILL.md 的 YAML 头部必须包含非空的 name 字段，例如: `name: My Skill`",
                )
            description = str(front_matter.get("description", "")).strip()
            body = "\n".join(body_lines).strip()
            return SkillArchiveMetadata(
                name=name,
                description=description,
                readme_text=body,
                front_matter=front_matter,
            )

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


def extract_and_validate_skill(zip_bytes: bytes) -> tuple[str, str, str]:
    """Validate a skill zip package and extract core metadata."""

    metadata = inspect_skill_archive(zip_bytes)
    return metadata.name, metadata.description, metadata.readme_text
