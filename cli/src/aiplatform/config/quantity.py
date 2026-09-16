"""Parse Kubernetes-style resource quantities (`500m`, `8Gi`)."""

import re

_CPU_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)?)(?P<milli>m)?$")
_MEM_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)?)(?P<unit>Ki|Mi|Gi|Ti|K|M|G|T)$")

_BINARY = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4}
_DECIMAL = {"K": 10**3, "M": 10**6, "G": 10**9, "T": 10**12}


def parse_cpu(raw: str | int | float) -> float:
    """Return CPU cores as a float. Accepts `2`, `1.5`, `500m`."""
    if isinstance(raw, bool):
        raise ValueError("cpu must be a number or a millicore string like '500m'")
    if isinstance(raw, int | float):
        cores = float(raw)
    else:
        m = _CPU_RE.match(raw.strip())
        if not m:
            raise ValueError(f"invalid cpu quantity {raw!r}; use e.g. 2, 1.5 or 500m")
        num = float(m.group("num"))
        if m.group("milli") and "." in m.group("num"):
            raise ValueError(f"invalid cpu quantity {raw!r}; millicores must be whole")
        cores = num / 1000 if m.group("milli") else num
    if cores <= 0:
        raise ValueError("cpu must be greater than zero")
    return cores


def parse_memory(raw: str) -> int:
    """Return bytes. Accepts binary (`Ki Mi Gi Ti`) and decimal (`K M G T`) suffixes."""
    if not isinstance(raw, str):
        raise ValueError("memory must be a string quantity like '8Gi'")
    m = _MEM_RE.match(raw.strip())
    if not m:
        raise ValueError(f"invalid memory quantity {raw!r}; use e.g. 512Mi, 8Gi or 1G")
    num = float(m.group("num"))
    unit = m.group("unit")
    mult = _BINARY.get(unit) or _DECIMAL[unit]
    size = int(num * mult)
    if size <= 0:
        raise ValueError("memory must be greater than zero")
    return size


def format_memory(size: int) -> str:
    """Human-readable binary units (`2.0Gi`)."""
    for unit, mult in reversed(list(_BINARY.items())):
        if size >= mult:
            return f"{size / mult:.1f}{unit}"
    return f"{size}B"
