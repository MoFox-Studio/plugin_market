"""Property tests for curation visibility."""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from plugin_market_backend.orm import AuthorORM, AuthorType, CurationEntryORM, utc_now
from plugin_market_backend.services._audience import AUDIENCE_VALUES, audience_matches
from plugin_market_backend.services.curation_service import is_visible


def _normalize(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _make_entry(
    *,
    enabled: bool,
    audience: str,
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> CurationEntryORM:
    now = utc_now()
    return CurationEntryORM(
      id=1,
      slot_type='featured_plugin',
      target_type='plugin',
      target_id='plug-a',
      signature_plugin_id=None,
      sort_order=0,
      enabled=enabled,
      starts_at=starts_at,
      ends_at=ends_at,
      audience=audience,
      display_meta={},
      created_by='admin',
      created_at=now,
      updated_at=now,
    )


def _make_viewer(kind: str) -> AuthorORM | None:
    if kind == 'anonymous':
        return None
    return AuthorORM(
        author_id=f'{kind}-viewer',
        github_user_id=f'gh-{kind}',
        github_login=kind,
        display_name=kind.title(),
        author_type=AuthorType.USER,
        is_admin=kind == 'admin',
    )


date_times = st.datetimes(timezones=st.one_of(st.none(), st.just(timezone.utc)))
audiences = st.sampled_from(sorted(AUDIENCE_VALUES))
viewer_kinds = st.sampled_from(['anonymous', 'user', 'admin'])


@settings(deadline=None, max_examples=200)
@given(
    enabled=st.booleans(),
    audience=audiences,
    starts_at=st.one_of(st.none(), date_times),
    ends_at=st.one_of(st.none(), date_times),
    now=date_times,
    viewer_kind=viewer_kinds,
    viewer_has_plugin=st.booleans(),
)
def test_is_visible_matches_schedule_and_audience_predicate(
    enabled: bool,
    audience: str,
    starts_at: datetime | None,
    ends_at: datetime | None,
    now: datetime,
    viewer_kind: str,
    viewer_has_plugin: bool,
) -> None:
    viewer = _make_viewer(viewer_kind)
    entry = _make_entry(
        enabled=enabled,
        audience=audience,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    within_start = starts_at is None or _normalize(starts_at) <= _normalize(now)
    within_end = ends_at is None or _normalize(now) <= _normalize(ends_at)
    expected = enabled and within_start and within_end and audience_matches(
        audience,
        viewer,
        viewer_has_plugin=viewer_has_plugin,
    )

    assert is_visible(entry, viewer, now, viewer_has_plugin=viewer_has_plugin) is expected


@settings(deadline=None, max_examples=100)
@given(
    audience=audiences,
    starts_at=st.one_of(st.none(), date_times),
    ends_at=st.one_of(st.none(), date_times),
    now=date_times,
    viewer_kind=viewer_kinds,
    viewer_has_plugin=st.booleans(),
)
def test_disabled_entries_are_never_visible(
    audience: str,
    starts_at: datetime | None,
    ends_at: datetime | None,
    now: datetime,
    viewer_kind: str,
    viewer_has_plugin: bool,
) -> None:
    viewer = _make_viewer(viewer_kind)
    entry = _make_entry(
        enabled=False,
        audience=audience,
        starts_at=starts_at,
        ends_at=ends_at,
    )

    assert is_visible(entry, viewer, now, viewer_has_plugin=viewer_has_plugin) is False