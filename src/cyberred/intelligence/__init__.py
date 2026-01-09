"""Vulnerability Intelligence Layer for Cyber-Red.

This module provides a unified interface for querying vulnerability
intelligence sources including CISA KEV, NVD, ExploitDB, Nuclei, and Metasploit.

Exports:
    IntelligenceSource: Abstract base class for all intelligence sources.
    IntelResult: Dataclass for intelligence query results.
    IntelPriority: Priority ranking constants for result ordering.
    IntelligenceAggregator: Unified interface to query all sources in parallel.
    CachedIntelligenceAggregator: Aggregator with Redis caching and request coalescing.
    IntelligenceErrorMetrics: Error and timeout tracking for sources.
    IntelligenceCache: Redis-backed intelligence cache.
    StigmergicIntelligencePublisher: Publishes intelligence to stigmergic layer.
    StigmergicIntelligenceSubscriber: Subscribes to stigmergic intelligence updates.

Usage:
    from cyberred.intelligence import IntelligenceAggregator, IntelResult
"""

from cyberred.intelligence.base import (
    IntelligenceSource,
    IntelPriority,
    IntelResult,
)
from cyberred.intelligence.aggregator import (
    IntelligenceAggregator,
    CachedIntelligenceAggregator,
)
from cyberred.intelligence.metrics import IntelligenceErrorMetrics
from cyberred.intelligence.cache import IntelligenceCache
from cyberred.intelligence.stigmergic import (
    StigmergicIntelligencePublisher,
    StigmergicIntelligenceSubscriber,
)

__all__ = [
    "IntelligenceSource",
    "IntelPriority",
    "IntelResult",
    "IntelligenceAggregator",
    "CachedIntelligenceAggregator",
    "IntelligenceErrorMetrics",
    "IntelligenceCache",
    "StigmergicIntelligencePublisher",
    "StigmergicIntelligenceSubscriber",
]
