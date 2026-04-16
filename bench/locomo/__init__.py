"""LoCoMo benchmark wrapper.

LoCoMo (Snap Research 2024) — long conversation memory benchmark. 10
multi-session conversations, 1986 questions across 5 categories
(single-hop, temporal, multi-hop, open-domain, adversarial).

Dataset: desire2020/locomo-serialized on HuggingFace
(serialized version of the original adymaharana/locomo dataset).
"""

from bench.locomo.runner import (
    LoCoMoReport,
    format_locomo_report,
    load_locomo,
    run_locomo,
)

__all__ = [
    "LoCoMoReport",
    "format_locomo_report",
    "load_locomo",
    "run_locomo",
]
