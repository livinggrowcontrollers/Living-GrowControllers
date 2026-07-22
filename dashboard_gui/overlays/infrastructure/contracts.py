# dashboard_gui/overlays/infrastructure/contracts.py

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SyncState(str, Enum):
    CONFIRMED = "green"
    DIRTY = "orange"
    RETRY = "retry"
    ERROR = "error"


@dataclass(frozen=True)
class OverlayKey:
    """Identity of one visible overlay, including generated instances."""

    kind: str
    instance_id: Optional[int] = None

    @property
    def command_instance_id(self):
        return self.instance_id
