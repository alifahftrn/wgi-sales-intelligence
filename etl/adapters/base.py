"""Source interface; no staging or business transformation here."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass(frozen=True)
class Dataset:
    name: str
    columns: tuple
    metadata: dict = field(default_factory=dict)

class BaseAdapter(ABC):
    source_type: str

    @abstractmethod
    def snapshot(self):
        """Context manager returning self; release source on exit."""

    @abstractmethod
    def datasets(self):
        """Return (list[Dataset], list[str] warnings)."""

    @abstractmethod
    def rows(self, dataset, batch_size):
        """Yield dicts with exactly the declared source columns."""

    @abstractmethod
    def metadata(self):
        """Return JSON-safe source metadata while snapshot is open."""
