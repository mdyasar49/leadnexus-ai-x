"""
SCIM 2.0 Directory Synchronization Engine (Phase 38)
Complies with RFC 7643 and RFC 7644 specifications for automated user and group provisioning/deprovisioning.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, List, Optional


class SCIMError(Exception):
    def __init__(self, message: str, status_code: int = 400, scim_type: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.scim_type = scim_type

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "detail": self.message,
            "status": str(self.status_code),
        }
        if self.scim_type:
            res["scimType"] = self.scim_type
        return res


class SCIMEngine:
    """Implements SCIM 2.0 Service Provider configurations, schemas, user and group formatting."""

    SCIM_USER_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:User"
    SCIM_GROUP_SCHEMA = "urn:ietf:params:scim:schemas:core:2.0:Group"
    SCIM_LIST_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:ListResponse"

    @classmethod
    def get_service_provider_config(cls) -> Dict[str, Any]:
        """Returns standard SCIM 2.0 ServiceProviderConfig."""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "documentationUri": "https://leadnexus.infogenx.com/docs/scim",
            "patch": {"supported": True},
            "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
            "filter": {"supported": True, "maxResults": 200},
            "changePassword": {"supported": False},
            "sort": {"supported": False},
            "etag": {"supported": True},
            "authenticationSchemes": [
                {
                    "name": "OAuth Bearer Token",
                    "description": "Authentication using Bearer Tokens",
                    "specUri": "http://www.rfc-editor.org/info/rfc6750",
                    "type": "oauthbearertoken",
                    "primary": True,
                }
            ],
        }

    @classmethod
    def format_scim_user(cls, user_record: Any) -> Dict[str, Any]:
        """Formats an internal SCIMUserRecord or User model into RFC 7643 SCIM User representation."""
        return {
            "schemas": [cls.SCIM_USER_SCHEMA],
            "id": str(user_record.id),
            "externalId": getattr(user_record, "external_id", str(user_record.id)),
            "userName": getattr(user_record, "user_name", getattr(user_record, "email", "")),
            "name": {
                "givenName": getattr(user_record, "given_name", getattr(user_record, "first_name", "")),
                "familyName": getattr(user_record, "family_name", getattr(user_record, "last_name", "")),
                "formatted": f"{getattr(user_record, 'given_name', '')} {getattr(user_record, 'family_name', '')}".strip(),
            },
            "emails": [
                {
                    "value": getattr(user_record, "email", ""),
                    "primary": True,
                    "type": "work",
                }
            ],
            "active": getattr(user_record, "active", True),
            "meta": {
                "resourceType": "User",
                "created": getattr(user_record, "created_at", datetime.now(timezone.utc)).isoformat() if hasattr(user_record, "created_at") else "",
                "lastModified": getattr(user_record, "updated_at", datetime.now(timezone.utc)).isoformat() if hasattr(user_record, "updated_at") else "",
                "location": f"/api/v1/identity/scim/v2/Users/{user_record.id}",
            },
        }

    @classmethod
    def format_scim_group(cls, group_record: Any) -> Dict[str, Any]:
        """Formats an internal SCIMGroupRecord into RFC 7643 SCIM Group representation."""
        raw_members = getattr(group_record, "members", []) or []
        members_formatted = [{"value": str(m), "$ref": f"/api/v1/identity/scim/v2/Users/{m}"} for m in raw_members]

        return {
            "schemas": [cls.SCIM_GROUP_SCHEMA],
            "id": str(group_record.id),
            "externalId": getattr(group_record, "external_id", str(group_record.id)),
            "displayName": getattr(group_record, "display_name", "Group"),
            "members": members_formatted,
            "meta": {
                "resourceType": "Group",
                "created": getattr(group_record, "created_at", datetime.now(timezone.utc)).isoformat() if hasattr(group_record, "created_at") else "",
                "lastModified": getattr(group_record, "updated_at", datetime.now(timezone.utc)).isoformat() if hasattr(group_record, "updated_at") else "",
                "location": f"/api/v1/identity/scim/v2/Groups/{group_record.id}",
            },
        }

    @classmethod
    def format_list_response(cls, resources: List[Dict[str, Any]], start_index: int = 1, total_count: Optional[int] = None) -> Dict[str, Any]:
        """Builds a SCIM ListResponse wrapper."""
        total = total_count if total_count is not None else len(resources)
        return {
            "schemas": [cls.SCIM_LIST_SCHEMA],
            "totalResults": total,
            "itemsPerPage": len(resources),
            "startIndex": start_index,
            "Resources": resources,
        }

    @classmethod
    def apply_patch_operations(cls, target_dict: Dict[str, Any], operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Applies SCIM RFC 7644 PATCH operations (add, replace, remove)."""
        updated = dict(target_dict)
        for op in operations:
            op_type = op.get("op", "").lower()
            path = op.get("path")
            value = op.get("value")

            if op_type in ("add", "replace"):
                if path:
                    # e.g., path: "active", value: false
                    updated[path] = value
                elif isinstance(value, dict):
                    # value is a dictionary of fields to update
                    updated.update(value)
            elif op_type == "remove":
                if path and path in updated:
                    del updated[path]

        return updated
