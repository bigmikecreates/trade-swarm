"""Persistence layer for experiment data."""

from lab.data.persistence.interfaces import (
    DataStore,
    ExperimentRecord,
    ExperimentStatus,
    TradeRecord,
    SignalRecord,
    EquityPoint,
    MetricRecord,
)

from lab.data.persistence.directory_store import DirectoryStore
from lab.data.persistence.redis_stream import RedisStreamProducer

try:
    from lab.data.persistence.postgres_store import PostgresStore
except ImportError:
    PostgresStore = None

try:
    from lab.data.persistence.chained_store import ChainedStore
except ImportError:
    ChainedStore = None

__all__ = [
    "DataStore",
    "ExperimentRecord",
    "ExperimentStatus",
    "TradeRecord",
    "SignalRecord",
    "EquityPoint",
    "MetricRecord",
    "DirectoryStore",
    "PostgresStore",
    "ChainedStore",
    "RedisStreamProducer",
]
