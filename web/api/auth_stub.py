"""Development stand-in. There is no password, no session, and no sign-in yet."""

from __future__ import annotations

import os

REFUSAL = (
    "VC Accountant online refuses to start outside development. "
    "Sign-in is not specified yet. There is no password."
)
BIND_HOST = "127.0.0.1"


def assert_development() -> None:
    if os.environ.get("VCA_ENV") != "development":
        raise SystemExit(REFUSAL)


def dev_member_name() -> str:
    name = os.environ.get("VCA_DEV_MEMBER", "").strip()
    if not name:
        raise SystemExit("Set VCA_DEV_MEMBER. See docs/ONLINE.md")
    return name
