"""
LeadNexus AI X - Phase 33: Enterprise Data Migration & Zero-Downtime Upgrades
API Versioning Manager: Version negotiation, client semver compatibility, and sunset lifecycle.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.migration import APIVersionContract


class APIVersioningManager:
    """Manages API contracts, backwards compatibility, and sunset deprecation enforcement."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def register_version(
        self,
        api_version: str,
        is_deprecated: bool = False,
        sunset_date: Optional[datetime] = None,
        breaking_changes: Optional[List[str]] = None,
        min_supported_client: str = "1.0.0",
    ) -> APIVersionContract:
        contract = self.db.query(APIVersionContract).filter(APIVersionContract.id == api_version).first()
        if not contract:
            contract = APIVersionContract(
                id=api_version,
                api_version=api_version,
                is_deprecated=is_deprecated,
                sunset_date=sunset_date,
                breaking_changes=breaking_changes or [],
                min_supported_client_version=min_supported_client,
            )
            self.db.add(contract)
        else:
            contract.is_deprecated = is_deprecated
            contract.sunset_date = sunset_date
            contract.breaking_changes = breaking_changes or []
            contract.min_supported_client_version = min_supported_client

        self.db.commit()
        self.db.refresh(contract)
        return contract

    def validate_request_version(
        self,
        api_version: str,
        client_version: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates API version.
        Returns: (is_supported, warning_header, error_message)
        """
        contract = self.db.query(APIVersionContract).filter(APIVersionContract.id == api_version).first()
        if not contract:
            return False, None, f"Unsupported API version '{api_version}'"

        now = datetime.now(timezone.utc)
        if contract.sunset_date:
            sunset_utc = contract.sunset_date.replace(tzinfo=timezone.utc if contract.sunset_date.tzinfo is None else contract.sunset_date.tzinfo)
            if now > sunset_utc:
                return False, None, f"API version '{api_version}' reached sunset on {contract.sunset_date.isoformat()} and is permanently retired"

        warning = None
        if contract.is_deprecated:
            warning = f"299 - API version '{api_version}' is deprecated. Sunset scheduled for {contract.sunset_date.isoformat() if contract.sunset_date else 'TBD'}"

        return True, warning, None

