"""Shared pure audience-matching predicate.

This module is intentionally pure: it does not import the database session, the
ORM, or any service. The single function it exposes is the canonical evaluator
for the ``audience`` enum used by ``announcements`` and ``curation_entries``.

Callers are responsible for resolving any side effects (such as "does the
viewer own at least one plugin?") and passing the result in via
``viewer_has_plugin``. This keeps the predicate trivially testable as a pure
function (see Properties 1 and 2).

The accepted audience values mirror the schemas literal:

* ``all``: visible to everybody, including anonymous viewers.
* ``logged_in``: visible to any authenticated viewer.
* ``anonymous``: visible only when the viewer is not authenticated.
* ``admins``: visible only to admins (``viewer.is_admin``).
* ``authors_with_plugin``: visible to authenticated viewers that own at least
  one plugin. Because this fact requires a database lookup, callers must pass
  the precomputed ``viewer_has_plugin`` flag (defaults to ``False``).
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
    """Return whether ``viewer`` should see content tagged with ``audience``.

    Args:
        audience: One of ``AUDIENCE_VALUES``. Unknown values evaluate to
            ``False`` rather than raising, so a misconfigured row never crashes
            the visibility loop. Validation is the schema layer's job.
        viewer: The current authenticated author, or ``None`` for anonymous.
        viewer_has_plugin: Whether the viewer owns or maintains at least one
            plugin. Required only for ``authors_with_plugin``; ignored
            otherwise. Callers must precompute this because ``audience_matches``
            does not touch the database.

    Returns:
        ``True`` if the viewer is in the audience.
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
