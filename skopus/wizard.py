"""Interactive wizard for `skopus init`.

Ten questions, ~5 minutes, personalized output. Falls back gracefully if
questionary is unavailable or stdin is not a TTY (e.g. during tests).
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import questionary

    HAS_QUESTIONARY = True
except ImportError:  # pragma: no cover
    HAS_QUESTIONARY = False


ROLE_CHOICES = [
    "solo-dev",
    "team-lead",
    "engineering-manager",
    "research",
    "founder",
    "bug-hunter",
    "other",
]

COMM_STYLE_CHOICES = ["terse", "detailed", "mix"]

AGENT_CHOICES = [
    "Claude Code",
    "Cursor",
    "Codex",
    "Aider",
    "Gemini CLI",
    "Copilot CLI",
    "OpenCode",
]

SEED_PROFILE_CHOICES = [
    "blank",
    "solo-dev",
    "team-lead",
    "research",
    "founder",
    "bug-hunter",
]

DEFAULT_NON_NEGOTIABLES_BY_ROLE: dict[str, list[str]] = {
    "solo-dev": [
        "Ship the atomic unit, then iterate",
        "YAGNI ruthlessly — no speculative abstractions",
        "Test what matters, skip what doesn't",
    ],
    "team-lead": [
        "Document decisions as ADRs",
        "Unblocking the team beats individual output",
        "Review critical paths, not every line",
    ],
    "engineering-manager": [
        "Create systems, not fires",
        "Protect focus time for the team",
        "Measure outcomes, not activity",
    ],
    "research": [
        "Every experiment is versioned and reproducible",
        "Honest about negative results",
        "Log the hypothesis before running the experiment",
    ],
    "founder": [
        "Premium quality — worth paying for, not just functional",
        "Business value first: revenue, cost cut, or time saved",
        "Plain language over technical jargon",
    ],
    "bug-hunter": [
        "Root cause over symptom",
        "TDD for bugfixes (red → green → commit)",
        "One PR per logical concern",
    ],
    "other": [
        "Evidence over assumption",
        "Memory first — check prior decisions before new research",
        "Systems thinking — no isolated fixes",
    ],
}


@dataclass
class WizardResult:
    """Result of the skopus init wizard."""

    name: str = "Developer"
    role: str = "solo-dev"
    stack: str = "Python, TypeScript"
    comm_style: str = "mix"
    non_negotiables: list[str] = field(
        default_factory=lambda: [
            "Evidence over assumption",
            "Memory first",
            "Systems thinking",
        ]
    )
    timezone: str = "UTC"
    agents: list[str] = field(default_factory=lambda: ["Claude Code"])
    vault_location: str = "~/Vault"
    graphify_scope: list[str] = field(default_factory=list)
    seed_profile: str = "blank"

    def as_context(self) -> dict[str, object]:
        """Convert to template rendering context, with date/time added."""
        ctx = asdict(self)
        now = datetime.now()
        ctx["date"] = now.strftime("%Y-%m-%d")
        ctx["time"] = now.strftime("%H:%M")
        return ctx


def _detect_timezone() -> str:
    """Detect the system timezone. Best-effort."""
    tz_env = os.environ.get("TZ")
    if tz_env:
        return tz_env
    tz_file = Path("/etc/timezone")
    if tz_file.exists():
        return tz_file.read_text().strip()
    return "UTC"


def default_result(name: str = "Developer", seed_profile: str = "blank") -> WizardResult:
    """Non-interactive default, used in tests and as a fallback.

    Seeds non-negotiables from the role map if the profile is role-shaped.
    """
    role = seed_profile if seed_profile in DEFAULT_NON_NEGOTIABLES_BY_ROLE else "other"
    return WizardResult(
        name=name,
        role=role,
        non_negotiables=DEFAULT_NON_NEGOTIABLES_BY_ROLE[role],
        timezone=_detect_timezone(),
        seed_profile=seed_profile,
    )


def run_wizard() -> WizardResult:
    """Run the interactive 10-question wizard.

    Falls back to defaults if not a TTY or questionary is missing.
    """
    if not sys.stdin.isatty() or not HAS_QUESTIONARY:
        return default_result()

    # Q1: name
    name = questionary.text(
        "What should I call you?", default="Developer"
    ).ask() or "Developer"

    # Q2: role
    role = questionary.select(
        "Your primary role?", choices=ROLE_CHOICES, default="solo-dev"
    ).ask() or "solo-dev"

    # Q3: stack
    stack = questionary.text(
        "Primary languages / stack (comma-separated)",
        default="Python, TypeScript",
    ).ask() or "Python, TypeScript"

    # Q4: communication style
    comm_style = questionary.select(
        "Communication style?", choices=COMM_STYLE_CHOICES, default="mix"
    ).ask() or "mix"

    # Q5: non-negotiables (seeded from role)
    role_defaults = DEFAULT_NON_NEGOTIABLES_BY_ROLE.get(role, DEFAULT_NON_NEGOTIABLES_BY_ROLE["other"])
    default_nn_text = "\n".join(role_defaults)
    nn_raw = questionary.text(
        "Top non-negotiables (one per line, edit as needed):",
        default=default_nn_text,
        multiline=True,
    ).ask() or default_nn_text
    non_negotiables = [line.strip() for line in nn_raw.splitlines() if line.strip()]

    # Q6: timezone
    timezone = questionary.text(
        "Your time zone?", default=_detect_timezone()
    ).ask() or _detect_timezone()

    # Q7: agents
    agents = questionary.checkbox(
        "Which agents do you use?",
        choices=AGENT_CHOICES,
    ).ask() or ["Claude Code"]

    # Q8: vault location
    vault_location = questionary.text(
        "Vault location", default="~/Vault"
    ).ask() or "~/Vault"

    # Q9: graphify scope
    graphify_raw = questionary.text(
        "Which codebases should be mapped on first graphify run? (comma-separated paths, or blank to skip for now)",
        default="",
    ).ask() or ""
    graphify_scope = [p.strip() for p in graphify_raw.split(",") if p.strip()]

    # Q10: seed profile
    seed_profile = questionary.select(
        "Initial seed profile?",
        choices=SEED_PROFILE_CHOICES,
        default=role if role in SEED_PROFILE_CHOICES else "blank",
    ).ask() or "blank"

    return WizardResult(
        name=name,
        role=role,
        stack=stack,
        comm_style=comm_style,
        non_negotiables=non_negotiables,
        timezone=timezone,
        agents=agents,
        vault_location=vault_location,
        graphify_scope=graphify_scope,
        seed_profile=seed_profile,
    )
