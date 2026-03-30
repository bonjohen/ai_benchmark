"""Collection coordination package — centralized coordinator with worker pool."""

from .coordinator import CollectionCoordinator
from .types import CoordFetchResult, FetchTask

__all__ = ["CollectionCoordinator", "CoordFetchResult", "FetchTask"]
