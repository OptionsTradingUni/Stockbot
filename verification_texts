# verification_texts.py
# Generates a large pool (~500) of realistic, HTML-ready verification lines
# for your Profit Flex Bot captions.

from __future__ import annotations
import random

# Core phrasing parts (kept generic across stocks, crypto, options)
_ACTIONS = [
    "validated", "confirmed", "cross-checked", "reconciled", "reviewed",
    "auto-verified", "double-checked", "audited", "matched", "verified"
]

_SUBJECTS = [
    "figures", "results", "profits", "performance", "numbers",
    "trade outcomes", "PnL figures", "session results"
]

_SOURCES = [
    "member trade records",
    "brokerage P/L exports",
    "order history data",
    "execution fills",
    "trade confirmations",
    "clearing statements",
    "brokerage statements",
    "daily PnL summaries",
    "tracked trading activity",
    "exchange fill reports",
    "timestamped trade logs",
    "imported brokerage reports",
    "internal audit checks",
    "submitted trade receipts",
    "member-submitted screenshots",
    "broker-generated PDFs",
    "trade verification logs",
    "platform activity records",
    "exported account history",
    "position close receipts",
    "closing order tickets",
    "execution receipts",
    "broker-provided CSVs",
    "statement summaries",
]

_QUALIFIERS = [
    "submitted by members",
    "from connected accounts",
    "via timestamped logs",
    "using session-linked IDs",
    "against historical records",
    "with internal consistency checks",
    "via routine review",
    "prior to posting",
    "against recent activity",
    "through standardized checks",
    "on a rolling basis",
    "before publication",
    "using batched review",
    "with sanity screening",
    "for consistency and accuracy",
    "per routine policy",
]

_PREFIXES = [
    "All", "Reported", "Posted", "Shared", "Submitted",
]

_METHOD_TAGS = [
    "automated review", "routine validation", "manual spot-checks",
    "aggregated logs", "multi-source reconciliation",
    "batch verification", "internal controls", "evidence-led checks",
]

# A few compact templates to keep output varied but clean for captions.
_TEMPLATES = [
    "💬 <i>{Prefix} {Subject} {action} via {Source}</i>",
    "💬 <i>{Prefix} {Subject} {action} against {Source}</i>",
    "💬 <i>{Prefix} {Subject} {action} using {Source}</i>",
    "💬 <i>{Prefix} {Subject} {action} with {Source}</i>",
    "💬 <i>{Prefix} {Subject} {action} from {Source}</i>",
    "💬 <i>{Prefix} {Subject} {action} through {Source}</i>",
    "💬 <i>{Prefix} {Subject} {action} via {Source} — {Qualifier}</i>",
    "💬 <i>{Prefix} {Subject} {action} against {Source} — {Qualifier}</i>",
    "💬 <i>{Prefix} {Subject} {action} using {Source} — {Qualifier}</i>",
    "💬 <i>{Prefix} {Subject} {action} through {Source} ({Method})</i>",
    "💬 <i>{Prefix} {Subject} {action} with {Source} ({Method})</i>",
]

def _title_case_keep_caps(text: str) -> str:
    """Title-case prefix words but keep reasonable capitalization."""
    return text if text.isupper() else text.title()

def build_verification_pool(target_size: int = 500, seed: int | None = None) -> list[str]:
    """
    Build a pool of ~target_size unique, HTML-ready lines.
    Uses combinatorial mixing + dedupe to stay compact in code.
    """
    if seed is not None:
        random.seed(seed)

    lines = set()

    # Expand combinations until we reach the target (with a cap)
    max_attempts = target_size * 20
    attempts = 0

    while len(lines) < target_size and attempts < max_attempts:
        attempts += 1

        action    = random.choice(_ACTIONS)
        subject   = random.choice(_SUBJECTS)
        source    = random.choice(_SOURCES)
        qualifier = random.choice(_QUALIFIERS)
        prefix    = _title_case_keep_caps(random.choice(_PREFIXES))
        method    = random.choice(_METHOD_TAGS)
        tpl       = random.choice(_TEMPLATES)

        line = tpl.format(
            Prefix=prefix,
            Subject=subject,
            action=action,
            Source=source,
            Qualifier=qualifier,
            Method=method,
        )

        # Minor variability: sometimes remove article "the" style clutter by design (none used now).
        # Keep short and caption-friendly.
        lines.add(line)

    # If we somehow fall short, pad with safe fallbacks
    fallback = "💬 <i>Figures verified via member trade records</i>"
    while len(lines) < target_size:
        lines.add(fallback)

    out = list(lines)
    random.shuffle(out)
    return out

# Public, prebuilt pool (defaults to ~500 lines)
VERIFICATION_LINES: list[str] = build_verification_pool(target_size=500)

def random_verification_line() -> str:
    """Return a random HTML-ready verification line."""
    if not VERIFICATION_LINES:
        return "💬 <i>Figures verified via member trade records</i>"
    return random.choice(VERIFICATION_LINES)

def sample(n: int = 5) -> list[str]:
    """Grab n random distinct lines for quick testing/demo."""
    if n <= 0:
        return []
    return random.sample(VERIFICATION_LINES, k=min(n, len(VERIFICATION_LINES)))
