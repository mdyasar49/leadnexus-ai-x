"""
LeadNexus AI X — Multi-Region Package
Phase 35 (ChatGPT Master Roadmap): Global Traffic Management, Replication & Failover
"""

from packages.multi_region.split_brain_guard import SplitBrainGuard, SplitBrainViolationError
from packages.multi_region.traffic_router import GlobalTrafficRouter, DataSovereigntyViolationError
from packages.multi_region.failover_orchestrator import FailoverOrchestrator, ReplicationLagThresholdExceededError

# Default platform singleton split-brain guard
global_split_brain_guard = SplitBrainGuard(initial_write_region="ap-southeast-2", initial_epoch=1)
global_traffic_router = GlobalTrafficRouter(global_split_brain_guard)
global_failover_orchestrator = FailoverOrchestrator(global_split_brain_guard)

__all__ = [
    "SplitBrainGuard",
    "SplitBrainViolationError",
    "GlobalTrafficRouter",
    "DataSovereigntyViolationError",
    "FailoverOrchestrator",
    "ReplicationLagThresholdExceededError",
    "global_split_brain_guard",
    "global_traffic_router",
    "global_failover_orchestrator",
]
