"""Smoke-test the service-layer skeleton.

This test guards the boundary that subsequent tasks (4-9) build on top of:

* every domain service module imports cleanly from a fresh interpreter,
* the package re-exports each service class as a single source of truth,
* there is no circular import between the new ``services`` package and the
  legacy ``plugin_market_backend.service`` module (which still exposes
  ``MarketService`` via direct definition),
* the shared helpers ``assert_can_edit_plugin_metadata`` and
  ``audience_matches`` are reachable from ``services``.
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
    """Each service module must import without side effects."""

    module = importlib.import_module(module_name)
    assert module is not None


def test_services_package_exports_service_classes() -> None:
    """The package surface exposes one class per domain plus shared helpers."""

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
        assert inspect.isclass(cls), f"{name} should be exported as a class"
        # Each service follows the MarketService pattern: __init__(self, session).
        signature = inspect.signature(cls.__init__)
        params = list(signature.parameters)
        assert params[:2] == ["self", "session"], (
            f"{name}.__init__ must take (self, session) like MarketService"
        )

    assert callable(services.assert_can_edit_plugin_metadata)
    assert callable(services.audience_matches)


def test_market_service_still_importable_from_service_module() -> None:
    """Existing call sites still resolve ``MarketService``."""

    legacy = importlib.import_module("plugin_market_backend.service")
    assert hasattr(legacy, "MarketService")


def test_no_circular_import_between_legacy_and_services() -> None:
    """Importing each service module in isolation must not pull in service.py.

    Property 8 (audit trail completeness) depends on ``services`` staying
    independent of ``plugin_market_backend.service``; otherwise a future
    refactor could accidentally reintroduce a cycle. We launch a fresh Python
    process per module and assert that ``plugin_market_backend.service`` did
    not get imported as a side effect.
    """

    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    for module in SERVICE_MODULES:
        script = (
            "import sys\n"
            f"import {module}\n"
            "assert 'plugin_market_backend.service' not in sys.modules, (\n"
            f"    'Importing {module} pulled in plugin_market_backend.service, '\n"
            "    'which would create a circular dependency.'\n"
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
            f"{module} failed isolation check:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )


def _clean_env() -> dict[str, str]:
    """Provide a minimal environment for isolated subprocess runs."""

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
