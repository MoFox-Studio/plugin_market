"""服务层骨架的冒烟测试。

验证后续任务（4–9）所依赖的边界：

* 每个领域服务模块都能在全新解释器中正常导入。
* 包重新导出各服务类，作为统一访问入口。
* 新的 services 包与旧的 plugin_market_backend.service 模块不存在循环导入；
  后者仍通过直接定义提供 MarketService。
* 可通过 services 访问共享辅助函数 assert_can_edit_plugin_metadata 和
  audience_matches。
"""

from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
from pathlib import Path

import pytest


SERVICE_MODULES: tuple[str, ...] = (
    "plugin_market_backend.services",
    "plugin_market_backend.services._audience",
    "plugin_market_backend.services._authz",
    "plugin_market_backend.services.profile_service",
    "plugin_market_backend.services.inline_edit_service",
    "plugin_market_backend.services.inbox_service",
    "plugin_market_backend.services.announcements_service",
    "plugin_market_backend.services.curation_service",
    "plugin_market_backend.services.bulk_ops_service",
)


@pytest.mark.parametrize("module_name", SERVICE_MODULES)
def test_service_modules_importable(module_name: str) -> None:
    """各服务模块应能无副作用地导入。"""
    module = importlib.import_module(module_name)
    assert module is not None


def test_services_package_exports_service_classes() -> None:
    """包应为每个领域公开一个服务类，并提供共享辅助函数。"""
    services = importlib.import_module("plugin_market_backend.services")

    expected = {
        "ProfileService",
        "InlineEditService",
        "InboxService",
        "AnnouncementsService",
        "CurationService",
        "BulkOpsService",
    }
    for name in expected:
        cls = getattr(services, name, None)
        assert inspect.isclass(cls), f"{name} 应作为类导出"
        # 各服务遵循 MarketService 的构造模式：__init__(self, session)。
        signature = inspect.signature(cls.__init__)
        params = list(signature.parameters)
        assert params[:2] == ["self", "session"], (
            f"{name}.__init__ 应与 MarketService 一样接收 (self, session)"
        )

    assert callable(services.assert_can_edit_plugin_metadata)
    assert callable(services.audience_matches)


def test_market_service_still_importable_from_service_module() -> None:
    """已有调用位置仍应能访问 MarketService。"""
    legacy = importlib.import_module("plugin_market_backend.service")
    assert hasattr(legacy, "MarketService")


def test_no_circular_import_between_legacy_and_services() -> None:
    """独立导入各服务模块时，不应连带导入 service.py。

    属性 8（审计轨迹完整性）依赖 services 与 plugin_market_backend.service
    保持独立，否则后续重构可能意外重新引入循环依赖。为每个模块启动全新的
    Python 进程，并断言未因副作用导入 plugin_market_backend.service。
    """
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    for module in SERVICE_MODULES:
        script = (
            "import sys\n"
            f"import {module}\n"
            "assert 'plugin_market_backend.service' not in sys.modules, (\n"
            f"    '导入 {module} 时连带导入了 plugin_market_backend.service，'\n"
            "    '这将造成循环依赖。'\n"
            ")\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(repo_root),
            env={**_clean_env(), "PYTHONPATH": str(src_root)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"{module} 未通过隔离检查：\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def _clean_env() -> dict[str, str]:
    """为隔离运行的子进程提供最小环境。

    Returns:
        仅包含必要系统变量的环境字典。
    """
    import os

    keep = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "HOMEPATH",
        "HOMEDRIVE",
        "LOCALAPPDATA",
        "APPDATA",
    }
    return {key: value for key, value in os.environ.items() if key in keep}
