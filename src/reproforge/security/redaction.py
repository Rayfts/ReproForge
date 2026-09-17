from __future__ import annotations

import re
from collections.abc import Iterable

_DEFAULT_PATTERNS = (
    re.compile(r"(?i)(authorization:\s*bearer\s+)[A-Za-z0-9._~+/-]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
)


def redact(text: str, *, secret_values: Iterable[str] = ()) -> str:
    output = text
    for secret in secret_values:
        if secret:
            output = output.replace(secret, "[REDACTED]")
    for pattern in _DEFAULT_PATTERNS:
        output = pattern.sub(
            lambda match: f"{match.group(1)}[REDACTED]" if match.groups() else "[REDACTED]",
            output,
        )
    return output
