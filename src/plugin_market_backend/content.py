"""Helpers for plugin market rich content and uploaded assets."""

from __future__ import annotations

import base64
import binascii
import io
from pathlib import Path

import bleach
from markdown import markdown
from PIL import Image, ImageOps

from plugin_market_backend.errors import ApiError

PLUGIN_MEDIA_DIR = Path("data") / "plugin_media"
PLUGIN_ICON_DIR = PLUGIN_MEDIA_DIR / "icons"

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