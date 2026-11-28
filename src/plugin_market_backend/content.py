"""插件市场富文本内容与上传资源辅助工具。"""

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

# 上传限制（必须与前端文档中约定的行为一致）。
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
    """从上传的技能 ZIP 包中解析出的元数据。"""

    name: str
    description: str
    readme_text: str
    front_matter: dict[str, Any]


def ensure_plugin_media_dirs() -> None:
    """确保插件媒体资源的存储目录存在。"""
    plugin_icon_dir().mkdir(parents=True, exist_ok=True)
    profile_background_dir().mkdir(parents=True, exist_ok=True)


def store_plugin_icon(plugin_id: str, icon_png_base64: str) -> str:
    """规范化并保存插件图标，返回其公开 URL。"""
    ensure_plugin_media_dirs()
    try:
        raw = base64.b64decode(icon_png_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ApiError(422, "INVALID_ICON", "插件图标必须是有效的 Base64 编码 PNG 数据。") from exc

    try:
        with Image.open(io.BytesIO(raw)) as image:
            if (image.format or "").upper() != "PNG":
                raise ApiError(422, "INVALID_ICON", "插件图标必须是 PNG 图片。")
            working = ImageOps.contain(image.convert("RGBA"), (512, 512), method=Image.Resampling.LANCZOS)
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(422, "INVALID_ICON", "无法将插件图标解码为 PNG 图片。") from exc

    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    offset = ((512 - working.width) // 2, (512 - working.height) // 2)
    canvas.paste(working, offset, working)
    normalized = canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)

    icon_path = plugin_icon_path(plugin_id)
    normalized.save(icon_path, format="PNG", optimize=True)
    return plugin_icon_url(plugin_id)


def delete_plugin_icon(plugin_id: str) -> None:
    """在插件清除图标时删除已存储的图标。"""
    icon_path = plugin_icon_path(plugin_id)
    if icon_path.exists():
        icon_path.unlink()


def plugin_icon_path(plugin_id: str) -> Path:
    """返回插件图标的存储路径。"""
    return plugin_icon_dir() / f"{plugin_id}.png"


def plugin_icon_url(plugin_id: str) -> str:
    """返回已存储插件图标的公开 URL。"""
    return f"/plugin-media/icons/{plugin_id}.png"


def normalize_readme_markdown(value: str | None) -> str | None:
    """在保存之前规范化 README Markdown。"""
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def render_readme_html(value: str | None) -> str | None:
    """将 README Markdown 渲染为经过安全清洗的 HTML。"""
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
# 多部分表单图片上传（图标 / 个人空间背景）
# ---------------------------------------------------------------------------

def store_plugin_icon_from_bytes(plugin_id: str, raw_bytes: bytes) -> str:
    """保存上传的插件图标。

    接受 PNG / JPEG / WEBP / GIF，等比缩放并放入透明画布，
    统一保存为 512×512 的 PNG 图片。

    Args:
        plugin_id: 插件标识符。
        raw_bytes: 上传的原始图片字节。

    Returns:
        图标的公开 URL。

    Raises:
        ApiError: 文件为空、超过大小限制、格式不受支持或无法解码。
    """
    ensure_plugin_media_dirs()
    if len(raw_bytes) == 0:
        raise ApiError(422, "INVALID_ICON", "插件图标文件为空。")
    if len(raw_bytes) > MAX_ICON_BYTES:
        raise ApiError(
            422,
            "INVALID_ICON",
            f"插件图标不得超过 {MAX_ICON_BYTES // 1024 // 1024} MiB。",
            {"max_bytes": MAX_ICON_BYTES, "received": len(raw_bytes)},
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            fmt = (image.format or "").upper()
            if fmt not in ALLOWED_IMAGE_FORMATS:
                raise ApiError(
                    422,
                    "INVALID_ICON",
                    "不支持此图片格式。允许的格式：PNG / JPEG / WEBP / GIF。",
                    {"format": fmt},
                )
            working = ImageOps.contain(
                image.convert("RGBA"), (512, 512), method=Image.Resampling.LANCZOS
            )
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(422, "INVALID_ICON", "无法将插件图标解码为图片。") from exc

    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    offset = ((512 - working.width) // 2, (512 - working.height) // 2)
    canvas.paste(working, offset, working)
    normalized = canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)

    icon_path = plugin_icon_path(plugin_id)
    normalized.save(icon_path, format="PNG", optimize=True)
    return plugin_icon_url(plugin_id)


def store_profile_background(author_id: str, raw_bytes: bytes) -> str:
    """保存上传的个人空间背景图片。

    接受 PNG / JPEG / WEBP，等比缩放至 1920×1080 范围内，
    兼顾桌面端主视觉展示与文件大小，并以质量 86 保存为 JPEG。

    Args:
        author_id: 作者标识符。
        raw_bytes: 上传的原始图片字节。

    Returns:
        背景图片的公开 URL。

    Raises:
        ApiError: 文件为空、超过大小限制、格式不受支持或无法解码。
    """
    ensure_plugin_media_dirs()
    if len(raw_bytes) == 0:
        raise ApiError(422, "PROFILE_BACKGROUND_EMPTY", "背景图片文件为空。")
    if len(raw_bytes) > MAX_BACKGROUND_BYTES:
        raise ApiError(
            422,
            "PROFILE_BACKGROUND_TOO_LARGE",
            f"背景图片不得超过 {MAX_BACKGROUND_BYTES // 1024 // 1024} MiB。",
            {"max_bytes": MAX_BACKGROUND_BYTES, "received": len(raw_bytes)},
        )

    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            fmt = (image.format or "").upper()
            if fmt not in {"PNG", "JPEG", "WEBP"}:
                raise ApiError(
                    422,
                    "PROFILE_BACKGROUND_INVALID_FORMAT",
                    "背景图片格式必须为 PNG / JPEG / WEBP。",
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
            "无法解码背景图片。",
        ) from exc

    safe_id = "".join(ch for ch in author_id if ch.isalnum() or ch in {"-", "_"}).strip("-_") or "anon"
    suffix = secrets.token_hex(4)
    filename = f"{safe_id}-{suffix}.jpg"
    target = profile_background_dir() / filename
    working.save(target, format="JPEG", quality=86, optimize=True)
    return f"/plugin-media/profile_backgrounds/{filename}"


def delete_profile_background_url(url: str | None) -> None:
    """尽力删除之前保存的个人空间背景资源。"""
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
# 技能包存储
# ---------------------------------------------------------------------------

MAX_SKILL_PACKAGE_BYTES = 10 * 1024 * 1024  # 10 MiB


def storage_root_dir() -> Path:
    """返回配置的存储根目录。"""
    return get_settings().storage_path


def plugin_media_dir() -> Path:
    """返回上传的公开媒体资源的根目录。"""
    return storage_root_dir() / "plugin_media"


def plugin_icon_dir() -> Path:
    """返回规范化插件图标的存储目录。"""
    return plugin_media_dir() / "icons"


def profile_background_dir() -> Path:
    """返回个人空间背景图片的存储目录。"""
    return plugin_media_dir() / "profile_backgrounds"


def skill_packages_dir() -> Path:
    """返回技能 ZIP 包的存储目录。"""
    return storage_root_dir() / "skill_packages"


PLUGIN_MEDIA_DIR = plugin_media_dir()


def ensure_skill_dirs() -> None:
    """确保技能包存储目录存在。"""
    skill_packages_dir().mkdir(parents=True, exist_ok=True)


def _validate_storage_segment(value: str, *, field_name: str, error_code: str) -> str:
    """校验逻辑标识符，确保可安全用于存储路径。"""
    normalized = value.strip()
    if not normalized:
        raise ApiError(422, error_code, f"{field_name} 不得为空。", {field_name: value})
    if normalized in {".", ".."}:
        raise ApiError(422, error_code, f"{field_name} 不得为 '.' 或 '..'。", {field_name: value})
    if "/" in normalized or "\\" in normalized:
        raise ApiError(
            422,
            error_code,
            f"{field_name} 不得包含路径分隔符。",
            {field_name: value},
        )
    if any(ord(char) < 32 or ord(char) == 127 for char in normalized):
        raise ApiError(
            422,
            error_code,
            f"{field_name} 不得包含控制字符。",
            {field_name: value},
        )
    return normalized


def validate_skill_id(skill_id: str) -> str:
    """校验当前 API 接受的逻辑技能 ID。"""
    return _validate_storage_segment(
        skill_id,
        field_name="skill_id",
        error_code="INVALID_SKILL_ID",
    )


def validate_skill_version(version: str) -> str:
    """校验当前 API 接受的逻辑技能版本。"""
    return _validate_storage_segment(
        version,
        field_name="version",
        error_code="INVALID_SKILL_VERSION",
    )


def _encode_storage_segment(value: str) -> str:
    """将任意标识符编码为单个安全的文件系统路径段。"""
    return quote(value, safe="")


def _decode_storage_segment(value: str) -> str:
    """将存储路径段解码为原始逻辑标识符。"""
    return unquote(value)


def _skill_storage_segments(owner_id: str, skill_id: str, version: str) -> tuple[str, str, str]:
    """返回技能包经过编码的存储路径段。"""
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
    """从已存储的技能包路径推断 ``(owner_id, skill_id, version)``。"""
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
    """返回已存储技能 ZIP 包的配套清单路径。"""
    return package_path.with_suffix(".json")


def iter_skill_package_files() -> list[tuple[str, Path]]:
    """以 ``(stored_path, absolute_path)`` 形式返回所有已存储的技能包文件。"""
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
    """返回技能包的相对存储路径。"""
    safe_owner_id, safe_skill_id, safe_version = _skill_storage_segments(owner_id, skill_id, version)
    return Path("skill_packages", safe_owner_id, safe_skill_id, f"{safe_version}.zip").as_posix()


def store_skill_package(owner_id: str, skill_id: str, version: str, zip_bytes: bytes) -> str:
    """保存技能 ZIP 包并返回存储路径。

    技能包存储在配置的根目录下，路径为
    ``skill_packages/{owner_id}/{skill_id}/{version}.zip``。
    路径段经过编码，因此逻辑标识符可以包含中文或大写字母。

    Args:
        owner_id: 技能所有者的标识符。
        skill_id: 技能标识符。
        version: 技能版本。
        zip_bytes: ZIP 包的原始字节。

    Returns:
        技能包相对于存储根目录的路径。
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
    """保存已存储技能包的配套 JSON 清单。"""
    package_path = resolve_skill_package_path(stored_package_path)
    manifest_path = skill_package_manifest_path(package_path)
    data = {"schema_version": SKILL_MANIFEST_SCHEMA_VERSION, **payload}
    manifest_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def load_skill_package_manifest(stored_package_path: str) -> dict[str, Any] | None:
    """加载已存储技能包可选的配套 JSON 清单。"""
    manifest_path = skill_package_manifest_path(resolve_skill_package_path(stored_package_path))
    if not manifest_path.exists():
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def resolve_skill_package_path(stored_path: str) -> Path:
    """将已存储的技能包路径解析为绝对文件系统路径。

    同时支持当前相对于存储根目录的格式，以及存储根目录规范化之前
    保存的 ``data/skill_packages/...`` 等旧格式。

    Args:
        stored_path: 已保存的技能包路径。

    Returns:
        首个存在的候选路径；均不存在时返回首个候选路径。
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
    """校验技能 ZIP 包并返回解析出的元数据。"""
    if len(zip_bytes) == 0:
        raise ApiError(422, "SKILL_PACKAGE_EMPTY", "技能包为空。")
    if len(zip_bytes) > MAX_SKILL_PACKAGE_BYTES:
        raise ApiError(
            422,
            "SKILL_PACKAGE_TOO_LARGE",
            f"技能包不得超过 {MAX_SKILL_PACKAGE_BYTES // 1024 // 1024} MiB。",
            {"max_bytes": MAX_SKILL_PACKAGE_BYTES, "received": len(zip_bytes)},
        )

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.startswith("/") or ".." in name.split("/"):
                    raise ApiError(
                        422,
                        "SKILL_PACKAGE_INSECURE_PATH",
                        f"技能包包含不安全的路径：{name!r}。",
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
                    "技能包的 ZIP 根目录必须包含 SKILL.md 文件（大小写须完全一致）。",
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
                    "SKILL.md 的 YAML 头部必须包含非空的 name 字段，例如: `name: 我的技能`",
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
            "技能包不是有效的 ZIP 归档文件。",
        ) from exc
    except UnicodeDecodeError as exc:
        raise ApiError(
            422,
            "SKILL_PACKAGE_ENCODING",
            "SKILL.md 必须是 UTF-8 编码的文本文件。",
        ) from exc


def extract_and_validate_skill(zip_bytes: bytes) -> tuple[str, str, str]:
    """校验技能 ZIP 包并提取核心元数据。"""
    metadata = inspect_skill_archive(zip_bytes)
    return metadata.name, metadata.description, metadata.readme_text
