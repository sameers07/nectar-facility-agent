from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Session:
    conversation: list[dict] = field(default_factory=list)
    investigation: dict[str, Any] = field(default_factory=dict)
    user_confirmation: Optional[bool] = None
    pending_action: Optional[dict] = None
