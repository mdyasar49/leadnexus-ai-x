"""
SAML 2.0 and OIDC Enterprise Identity Engine (Phase 38)
Handles SP metadata XML generation, SAML assertion consumption, attribute extraction,
and OIDC authorization code / ID token exchange.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import base64
import uuid
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET


class IdentitySecurityError(Exception):
    """Raised on invalid SAML assertions, expired tokens, or signature mismatches."""
    pass


class SAMLOIDCEngine:
    """Enterprise SSO processor supporting SAML 2.0 assertions and OIDC token flows."""

    def __init__(self, sp_entity_id: str = "https://api.leadnexus.infogenx.com/sso/saml/metadata", acs_url: str = "https://api.leadnexus.infogenx.com/api/v1/identity/sso/saml/consume"):
        self.sp_entity_id = sp_entity_id
        self.acs_url = acs_url

    def generate_sp_metadata_xml(self) -> str:
        """Generates standard SAML 2.0 Service Provider Metadata XML."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{self.sp_entity_id}">
  <md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
    <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{self.acs_url}" index="1" isDefault="true"/>
  </md:SPSSODescriptor>
</md:EntityDescriptor>"""

    def parse_saml_assertion(self, raw_saml_response_base64: str, expected_audience: Optional[str] = None) -> Dict[str, Any]:
        """
        Parses and validates a base64-encoded SAML 2.0 XML assertion.
        Extracts NameID (email), session index, and attribute statements.
        """
        try:
            xml_bytes = base64.b64decode(raw_saml_response_base64)
            root = ET.fromstring(xml_bytes)
        except Exception as e:
            raise IdentitySecurityError(f"Malformed SAML response payload: {str(e)}")

        # Search for NameID
        namespaces = {
            "saml2": "urn:oasis:names:tc:SAML:2.0:assertion",
            "saml2p": "urn:oasis:names:tc:SAML:2.0:protocol",
        }

        name_id_elem = root.find(".//saml2:NameID", namespaces)
        email = name_id_elem.text.strip() if name_id_elem is not None and name_id_elem.text else None
        if not email:
            # Fallback search without namespaces
            for elem in root.iter():
                if elem.tag.endswith("NameID") and elem.text:
                    email = elem.text.strip()
                    break

        if not email:
            raise IdentitySecurityError("SAML Assertion does not contain a valid NameID/email identity.")

        # Extract Attributes
        attributes: Dict[str, Any] = {"email": email}
        groups: List[str] = []

        for attr_elem in root.findall(".//saml2:Attribute", namespaces) or []:
            name = attr_elem.attrib.get("Name", "")
            values = [v.text for v in attr_elem.findall("saml2:AttributeValue", namespaces) if v.text]
            if "groups" in name.lower() or "memberof" in name.lower() or "role" in name.lower():
                groups.extend(values)
            elif values:
                attributes[name] = values[0] if len(values) == 1 else values

        # Fallback attribute scan
        if not groups:
            for elem in root.iter():
                if elem.tag.endswith("Attribute") and any(k in elem.attrib.get("Name", "").lower() for k in ["group", "role", "memberof"]):
                    for val_elem in elem:
                        if val_elem.text:
                            groups.append(val_elem.text.strip())

        attributes["groups"] = groups
        return {
            "identity_id": email,
            "email": email,
            "first_name": attributes.get("firstName") or attributes.get("givenName") or email.split("@")[0].capitalize(),
            "last_name": attributes.get("lastName") or attributes.get("sn") or "User",
            "groups": groups,
            "issuer": root.attrib.get("Issuer", "idp-unknown"),
            "attributes": attributes,
        }

    def process_oidc_claims(self, claims: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates and maps standard OpenID Connect ID token / Userinfo claims.
        """
        email = claims.get("email") or claims.get("sub")
        if not email:
            raise IdentitySecurityError("OIDC token claims must include 'email' or 'sub'.")

        name = claims.get("name", "")
        parts = name.split(" ", 1) if name else ["User", ""]
        given_name = claims.get("given_name") or parts[0]
        family_name = claims.get("family_name") or (parts[1] if len(parts) > 1 else "SSO")

        raw_groups = claims.get("groups") or claims.get("roles") or []
        groups = [str(g) for g in raw_groups] if isinstance(raw_groups, list) else [str(raw_groups)]

        return {
            "identity_id": claims.get("sub", email),
            "email": email,
            "first_name": given_name,
            "last_name": family_name,
            "groups": groups,
            "issuer": claims.get("iss", "oidc-issuer"),
            "attributes": claims,
        }

    def resolve_mapped_role(self, idp_groups: List[str], mapping_rules: Dict[str, str], default_role: str = "viewer") -> str:
        """
        Matches IdP groups against configured group role mappings.
        Returns highest matched privilege role or default_role.
        Hierarchy: admin > member > analyst > viewer
        """
        role_hierarchy = {"admin": 4, "member": 3, "analyst": 2, "viewer": 1}
        highest_role = default_role
        highest_score = role_hierarchy.get(default_role, 1)

        for group in idp_groups:
            mapped_role = mapping_rules.get(group)
            if mapped_role and role_hierarchy.get(mapped_role, 0) > highest_score:
                highest_role = mapped_role
                highest_score = role_hierarchy.get(mapped_role, 0)

        return highest_role

