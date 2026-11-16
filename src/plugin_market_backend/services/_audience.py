"""提供共享的纯函数受众匹配判断。

本模块在运行时不导入数据库会话、ORM 或任何服务，以保持纯函数特性。
唯一公开的函数统一判断 ``announcements`` 和 ``curation_entries`` 使用的
``audience`` 枚举值。

调用方负责处理依赖外部状态的查询（例如访问者是否拥有至少一个插件），
并通过 ``viewer_has_plugin`` 传入结果，使此判断易于作为纯函数测试
（参见性质 1 和 2）。

支持的受众值与数据模型中的字面量一致：

* ``all``：所有人可见，包括匿名访问者。
* ``logged_in``：所有已认证访问者可见。
* ``anonymous``：仅未认证访问者可见。
* ``admins``：仅管理员可见（``viewer.is_admin``）。
* ``authors_with_plugin``：拥有至少一个插件的已认证访问者可见。
  此信息需要查询数据库，因此调用方必须传入预先计算的
  ``viewer_has_plugin`` 标记（默认为 ``False``）。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from plugin_market_backend.orm import AuthorORM


AUDIENCE_VALUES: Final[frozenset[str]] = frozenset(
    {"all", "logged_in", "anonymous", "admins", "authors_with_plugin"}
)


def audience_matches(
    audience: str,
    viewer: "AuthorORM | None",
    *,
    viewer_has_plugin: bool = False,
) -> bool:
    """判断 ``viewer`` 是否应看到标记为 ``audience`` 的内容。

    Args:
        audience: ``AUDIENCE_VALUES`` 中的受众值。未知值返回 ``False``，
            不抛出异常，避免配置错误的记录中断可见性判断；值校验由数据模型层负责。
        viewer: 当前已认证作者，匿名访问时为 ``None``。
        viewer_has_plugin: 访问者是否拥有或维护至少一个插件。仅在
            ``authors_with_plugin`` 场景使用，其他场景忽略。此函数不访问数据库，
            因此调用方必须预先计算该值。

    Returns:
        访问者属于指定受众时返回 ``True``。
    """
    if audience == "all":
        return True
    if audience == "logged_in":
        return viewer is not None
    if audience == "anonymous":
        return viewer is None
    if audience == "admins":
        return viewer is not None and bool(getattr(viewer, "is_admin", False))
    if audience == "authors_with_plugin":
        return viewer is not None and viewer_has_plugin
    return False
