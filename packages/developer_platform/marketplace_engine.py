"""
LeadNexus AI X - Phase 28: Enterprise Developer Platform
Marketplace Engine: Catalog discovery, security verification, automated AST review, and connector installations.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.models.developer_platform import (
    Connector,
    ConnectorInstallation,
    ConnectorVersion,
    MarketplaceListing,
    MarketplaceTrustLevel,
)
from packages.developer_platform.connector_sdk import ConnectorManifest, ConnectorSecurityScanner


class MarketplaceSecurityReviewer:
    """Automated security gatekeeper evaluating third-party connector packages before listing."""

    @classmethod
    def evaluate_package(
        cls,
        manifest_data: Dict[str, Any],
        source_code: Optional[str] = None,
    ) -> Tuple[bool, List[str], str]:
        """
        Validates connector manifest and scans code.
        Returns: (is_approved, issues, security_review_status)
        """
        issues: List[str] = []

        # 1. Manifest structure check
        try:
            manifest = ConnectorManifest.from_dict(manifest_data)
        except Exception as e:
            return False, [f"Invalid manifest: {str(e)}"], "REJECTED"

        # 2. Check for restricted permissions
        for perm in manifest.required_permissions:
            if perm in ("admin:all", "database:raw_sql", "system:root"):
                issues.append(f"Permission '{perm}' is strictly forbidden for marketplace connectors.")

        # 3. Source code AST analysis if provided
        if source_code:
            code_safe, code_issues = ConnectorSecurityScanner.scan_code(source_code)
            if not code_safe:
                issues.extend(code_issues)

        # 4. Outbound domain sanity
        for domain in manifest.allowed_domains:
            if domain in ("localhost", "127.0.0.1", "169.254.169.254", "internal"):
                issues.append(f"Domain '{domain}' is blocked by enterprise SSRF security policy.")

        if issues:
            return False, issues, "REJECTED"

        return True, [], "APPROVED"


class MarketplaceEngine:
    """Manages marketplace listings, connector publishing, and workspace installations."""

    def __init__(self, db_session: Any):
        self.db = db_session

    def publish_connector(
        self,
        connector_id: str,
        name: str,
        version: str,
        category: str,
        description: str,
        author_name: str,
        manifest: Dict[str, Any],
        trust_level: MarketplaceTrustLevel = MarketplaceTrustLevel.COMMUNITY,
        source_code: Optional[str] = None,
    ) -> Tuple[Connector, MarketplaceListing, str]:
        """
        Submits and verifies a connector for listing in the enterprise marketplace.
        """
        # Security evaluation
        is_approved, issues, review_status = MarketplaceSecurityReviewer.evaluate_package(
            manifest_data=manifest,
            source_code=source_code,
        )

        if not is_approved:
            raise ValueError(f"Security review rejected connector: {'; '.join(issues)}")

        # Create or update Connector
        connector = self.db.query(Connector).filter(Connector.id == connector_id).first()
        if not connector:
            connector = Connector(
                id=connector_id,
                name=name,
                version=version,
                category=category,
                trust_level=trust_level.value if isinstance(trust_level, MarketplaceTrustLevel) else trust_level,
                manifest=manifest,
                permissions=manifest.get("required_permissions", []),
                is_published=True,
                is_verified=(trust_level in (MarketplaceTrustLevel.OFFICIAL, MarketplaceTrustLevel.VERIFIED_PARTNER)),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(connector)
        else:
            connector.version = version
            connector.manifest = manifest
            connector.permissions = manifest.get("required_permissions", [])

        # Create marketplace listing
        listing = self.db.query(MarketplaceListing).filter(MarketplaceListing.connector_id == connector_id).first()
        if not listing:
            listing = MarketplaceListing(
                id=str(uuid.uuid4()),
                connector_id=connector_id,
                title=name,
                description=description,
                category=category,
                author_name=author_name,
                rating=5.0,
                download_count=0,
                security_review_status=review_status,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(listing)
        else:
            listing.title = name
            listing.description = description
            listing.security_review_status = review_status

        self.db.commit()
        self.db.refresh(connector)
        self.db.refresh(listing)
        return connector, listing, review_status

    def list_marketplace_connectors(
        self,
        category: Optional[str] = None,
        trust_level: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries published connectors and their listings."""
        query = self.db.query(Connector, MarketplaceListing).join(
            MarketplaceListing, Connector.id == MarketplaceListing.connector_id
        ).filter(Connector.is_published == True)

        if category:
            query = query.filter(Connector.category == category)
        if trust_level:
            query = query.filter(Connector.trust_level == trust_level)

        results = []
        for conn, listing in query.all():
            results.append({
                "connector_id": conn.id,
                "name": conn.name,
                "version": conn.version,
                "category": conn.category,
                "trust_level": conn.trust_level,
                "is_verified": conn.is_verified,
                "title": listing.title,
                "description": listing.description,
                "author": listing.author_name,
                "rating": listing.rating,
                "download_count": listing.download_count,
                "required_permissions": conn.permissions,
            })
        return results

    def install_connector(
        self,
        workspace_id: str,
        connector_id: str,
        configuration: Optional[Dict[str, Any]] = None,
    ) -> ConnectorInstallation:
        """Installs a connector into a workspace."""
        connector = self.db.query(Connector).filter(Connector.id == connector_id).first()
        if not connector:
            raise ValueError(f"Connector '{connector_id}' not found.")

        # Check existing installation
        existing = self.db.query(ConnectorInstallation).filter(
            ConnectorInstallation.workspace_id == workspace_id,
            ConnectorInstallation.connector_id == connector_id,
        ).first()

        if existing:
            existing.status = "ACTIVE"
            existing.configuration = configuration or {}
            self.db.commit()
            self.db.refresh(existing)
            return existing

        installation = ConnectorInstallation(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            connector_id=connector_id,
            status="ACTIVE",
            configuration=configuration or {},
            installed_at=datetime.now(timezone.utc),
        )
        self.db.add(installation)

        # Increment download counter on listing
        listing = self.db.query(MarketplaceListing).filter(MarketplaceListing.connector_id == connector_id).first()
        if listing:
            listing.download_count = (listing.download_count or 0) + 1

        self.db.commit()
        self.db.refresh(installation)
        return installation

    def uninstall_connector(self, installation_id: str) -> bool:
        """Uninstalls a connector safely while preserving canonical database records."""
        installation = self.db.query(ConnectorInstallation).filter(
            ConnectorInstallation.id == installation_id
        ).first()
        if not installation:
            return False

        installation.status = "UNINSTALLED"
        self.db.commit()
        return True

