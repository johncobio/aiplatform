"""Monthly cost ESTIMATES from the price table in policy/prices.yaml.

Kubernetes workloads are priced by memory share of a Graviton node at their
maximum replica count; Terraform environments by instance type defaults and
expensive resource types. Every line item names its inputs so a reviewer can
disagree with the assumptions.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from aiplatform.config.loader import load_config
from aiplatform.errors import ConfigError


@dataclass
class LineItem:
    description: str
    monthly_usd: float


@dataclass
class CostEstimate:
    items: list[LineItem] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(i.monthly_usd for i in self.items), 2)

    def markdown(self) -> str:
        rows = ["| Item | Est. $/month |", "|---|---|"]
        rows += [f"| {i.description} | {i.monthly_usd:.2f} |" for i in self.items]
        rows.append(f"| **Total (estimate)** | **{self.total:.2f}** |")
        return "\n".join(rows)


def load_prices(repo: Path) -> dict:
    return yaml.safe_load((repo / "policy" / "prices.yaml").read_text())


def load_limits(repo: Path) -> dict:
    return yaml.safe_load((repo / "policy" / "data" / "limits.yaml").read_text())["limits"]


def estimate(repo: Path) -> CostEstimate:
    prices = load_prices(repo)
    hours = prices["hours_per_month"]
    per_gib = prices["per_gib_hour_usd"]
    est = CostEstimate()

    for cfg_path in sorted(repo.glob("services/*/aiplatform.yaml")):
        try:
            cfg = load_config(cfg_path)
        except ConfigError as e:
            raise ConfigError(f"cannot estimate {cfg_path}: {e}") from None
        gib = cfg.memory_bytes / 1024**3
        replicas = max(1, cfg.autoscaling.max)
        monthly = round(replicas * gib * per_gib * hours, 2)
        est.items.append(
            LineItem(
                f"workload `{cfg.name}` ({cfg.environment}): {replicas} × "
                f"{gib:g} GiB × ${per_gib}/GiB-h",
                monthly,
            )
        )

    for var_file in sorted(repo.glob("infra/terraform/environments/*/variables.tf")):
        env = var_file.parent.name
        text = var_file.read_text()
        enabled = _default(text, "enable_compute")
        itype = _default(text, "instance_type")
        if itype:
            price = prices["hourly_usd"]["instance"].get(itype.strip('"'))
            if price is None:
                est.items.append(LineItem(f"terraform `{env}`: unknown instance type {itype}", 0.0))
            elif enabled == "true":
                est.items.append(
                    LineItem(
                        f"terraform `{env}`: 1 × {itype} × ${price}/h", round(price * hours, 2)
                    )
                )
            else:
                est.items.append(
                    LineItem(f"terraform `{env}`: {itype} (enable_compute=false, not running)", 0.0)
                )
        main = var_file.parent / "main.tf"
        if main.exists():
            body = main.read_text()
            for res, key, label in (
                ("aws_nat_gateway", "nat_gateway", "NAT gateway"),
                ("aws_eks_cluster", "eks_cluster", "EKS control plane"),
                ("aws_lb", "alb", "load balancer"),
            ):
                n = len(re.findall(rf'resource\s+"{res}"', body))
                if n:
                    est.items.append(
                        LineItem(
                            f"terraform `{env}`: {n} × {label}",
                            round(n * prices["hourly_usd"][key] * hours, 2),
                        )
                    )
    return est


def _default(text: str, var: str) -> str | None:
    m = re.search(rf'variable\s+"{var}"\s*\{{.*?default\s*=\s*("?[^\s"]+"?)', text, re.S)
    return m.group(1) if m else None
