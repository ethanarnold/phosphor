"""Route registration order regression tests.

FastAPI does first-match (not longest-prefix) routing, so any route with a
literal segment must be registered before a sibling route whose corresponding
segment is a dynamic parameter. When that order gets inverted, the dynamic
route swallows the request and returns 422 on type-coerce failure (e.g.
"ranked" is not a valid UUID), which is what happens if
`opportunities.router` is included before `matching.router`.
"""

from app.main import app


def _route_index(path: str) -> int:
    """Index of the first registered route whose path equals `path`."""
    for i, route in enumerate(app.routes):
        if getattr(route, "path", None) == path:
            return i
    raise AssertionError(f"route not registered: {path}")


def test_ranked_opportunities_is_registered_before_opportunity_by_id() -> None:
    """`/opportunities/ranked` must win over `/opportunities/{opp_id}`."""
    ranked = _route_index("/api/v1/labs/{lab_id}/opportunities/ranked")
    by_id = _route_index("/api/v1/labs/{lab_id}/opportunities/{opp_id}")
    assert ranked < by_id, (
        "matching.router must be registered before opportunities.router so "
        "that GET /opportunities/ranked isn't swallowed by the UUID-typed "
        "GET /opportunities/{opp_id}"
    )
