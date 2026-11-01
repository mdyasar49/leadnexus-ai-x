"""
Enterprise Data Fabric Package (Phase 39)
Unified Data Access Layer, Lineage, Data Catalog, Quality Scoring & Policy Enforcement
"""

from packages.data_fabric.unified_contracts import UnifiedDataContractEngine, ContractValidationError
from packages.data_fabric.federated_access import FederatedAccessRouter
from packages.data_fabric.data_lineage_tracker import DataLineageTracker, LineageCycleError
from packages.data_fabric.quality_evaluator import DataQualityEvaluator
from packages.data_fabric.policy_enforcer import DataPolicyEnforcer

__all__ = [
    "UnifiedDataContractEngine",
    "ContractValidationError",
    "FederatedAccessRouter",
    "DataLineageTracker",
    "LineageCycleError",
    "DataQualityEvaluator",
    "DataPolicyEnforcer",
]

