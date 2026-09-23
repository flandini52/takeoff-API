"""Access-control seam.

require_access() is the single place auth will be wired in later (e.g.
st.login()) — every page calls it, so enabling auth becomes a change in
this one function instead of every page. No-op for now: no authentication
in this phase.
"""


def require_access() -> None:
    pass
