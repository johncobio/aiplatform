"""Version comparison for the already deployed, stateless demo form."""

import re

EMAIL = re.compile(
    r"[a-z0-9_+%-]+(?:\.[a-z0-9_+%-]+)*@"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
    re.IGNORECASE | re.ASCII,
)


def compare_versions(email):
    email = email.strip()
    return {"version1": bool(email), "version2": EMAIL.fullmatch(email) is not None}
