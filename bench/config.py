"""Benchmark configuration — lens configs, drivers, metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class LensConfig(str, Enum):
    """The five lens configurations for ablation studies."""

    VANILLA = "vanilla"  # no skopus context
    CHARTER = "charter"  # +charter only
    CHARTER_MEMORY = "charter+memory"  # +charter +memory
    CHARTER_MEMORY_VAULT = "charter+memory+vault"  # +C +M +V
    FULL = "full"  # +C +M +V +graph (full skopus)

    @classmethod
    def all_configs(cls) -> list[LensConfig]:
        return [
            cls.VANILLA,
            cls.CHARTER,
            cls.CHARTER_MEMORY,
            cls.CHARTER_MEMORY_VAULT,
            cls.FULL,
        ]

    @property
    def display_name(self) -> str:
        return {
            LensConfig.VANILLA: "vanilla",
            LensConfig.CHARTER: "+charter",
            LensConfig.CHARTER_MEMORY: "+charter +memory",
            LensConfig.CHARTER_MEMORY_VAULT: "+charter +memory +vault",
            LensConfig.FULL: "full skopus",
        }[self]


@dataclass
class BenchmarkResult:
    """Result of running a single benchmark scenario."""

    scenario_id: str
    lens: LensConfig
    passed: bool
    score: float  # 0.0 – 1.0
    notes: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


@dataclass
class BenchmarkReport:
    """Aggregate report across scenarios for one benchmark + lens config."""

    benchmark_name: str
    lens: LensConfig
    results: list[BenchmarkResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def mean_score(self) -> float:
        return sum(r.score for r in self.results) / self.total if self.total else 0.0

    @property
    def total_tokens(self) -> int:
        return sum(r.tokens_in + r.tokens_out for r in self.results)

    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.results)


def bench_results_dir(project_root: Path | None = None) -> Path:
    """Where benchmark results get written."""
    root = project_root or Path.cwd()
    return root / "bench" / "results"
