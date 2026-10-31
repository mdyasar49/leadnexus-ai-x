import base64
import hashlib
import hmac
import ipaddress
import os
import re
import secrets
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse


class SSRFProtectionError(PermissionError):
    """Raised when an outbound request attempts to access an unsafe or private destination."""
    pass


class SecretManager:
    """
    Encrypts and decrypts integration credentials and tokens.
    Raw secrets are never exposed in plaintext across logs or API responses.
    """

    _MASTER_SALT = b"leadnexus_enterprise_salt_2026"

    @classmethod
    def _get_key(cls) -> bytes:
        # In production this loads from KMS / Secret Manager
        secret = os.environ.get("LEADNEXUS_ENCRYPTION_KEY", "leadnexus_default_secure_vault_key_32chars")
        return hashlib.sha256(secret.encode() + cls._MASTER_SALT).digest()

    @classmethod
    def encrypt_secret(cls, plaintext: str) -> str:
        """Encrypts plaintext string into URL-safe base64 encoded ciphertext."""
        if not plaintext:
            return ""
        key = cls._get_key()
        nonce = secrets.token_bytes(12)
        # XOR keystream with nonce and key for portable cipher
        stream = hashlib.sha256(key + nonce).digest()
        cipher_bytes = bytearray()
        plain_bytes = plaintext.encode("utf-8")
        for i, b in enumerate(plain_bytes):
            cipher_bytes.append(b ^ stream[i % len(stream)])
        payload = nonce + bytes(cipher_bytes)
        return "enc_" + base64.urlsafe_b64encode(payload).decode("ascii")

    @classmethod
    def decrypt_secret(cls, encrypted_str: str) -> str:
        """Decrypts ciphertext string back into original plaintext."""
        if not encrypted_str or not encrypted_str.startswith("enc_"):
            return encrypted_str
        try:
            raw = base64.urlsafe_b64decode(encrypted_str[4:].encode("ascii"))
            nonce = raw[:12]
            ciphertext = raw[12:]
            key = cls._get_key()
            stream = hashlib.sha256(key + nonce).digest()
            plain_bytes = bytearray()
            for i, b in enumerate(ciphertext):
                plain_bytes.append(b ^ stream[i % len(stream)])
            return plain_bytes.decode("utf-8")
        except Exception:
            return ""


class OAuth2FlowHandler:
    """
    Handles secure OAuth 2.0 Authorization Code flow with PKCE,
    state verification, and strict redirect URI whitelisting.
    """

    ALLOWED_REDIRECT_DOMAINS: Set[str] = {
        "app.leadnexus.ai",
        "api.leadnexus.ai",
        "localhost",
        "127.0.0.1",
    }

    @classmethod
    def generate_pkce_pair(cls) -> Dict[str, str]:
        """Generates code_verifier and S256 code_challenge."""
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return {
            "code_verifier": verifier,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }

    @classmethod
    def generate_state_token(cls, workspace_id: str, provider_id: str) -> str:
        """Generates a secure cryptographically signed state token."""
        rand = secrets.token_hex(16)
        payload = f"{workspace_id}:{provider_id}:{rand}"
        sig = hmac.new(b"state_signing_key", payload.encode(), hashlib.sha256).hexdigest()[:16]
        return f"{payload}:{sig}"

    @classmethod
    def validate_state_token(cls, state_token: str, expected_workspace_id: str, expected_provider_id: str) -> bool:
        """Validates state token to prevent OAuth CSRF attacks."""
        parts = state_token.split(":")
        if len(parts) != 4:
            return False
        ws_id, prov_id, rand, sig = parts
        if ws_id != expected_workspace_id or prov_id != expected_provider_id:
            return False
        expected_payload = f"{ws_id}:{prov_id}:{rand}"
        expected_sig = hmac.new(b"state_signing_key", expected_payload.encode(), hashlib.sha256).hexdigest()[:16]
        return hmac.compare_digest(sig, expected_sig)

    @classmethod
    def validate_redirect_uri(cls, redirect_uri: str) -> bool:
        """Ensures redirect URI matches authorized platform domains."""
        if not redirect_uri:
            return False
        parsed = urlparse(redirect_uri)
        if parsed.scheme not in ("https", "http"):
            return False
        host = (parsed.hostname or "").lower()
        return host in cls.ALLOWED_REDIRECT_DOMAINS or host.endswith(".leadnexus.ai")


class APIKeyManager:
    """
    Generates, hashes, and validates API keys with scoped permission boundaries.
    """

    PREFIX = "lnx_live_"

    @classmethod
    def generate_api_key(cls, workspace_id: str, scopes: List[str]) -> Dict[str, Any]:
        """Generates a new API key, returning the plaintext key once and storing the hash."""
        random_bytes = secrets.token_urlsafe(32)
        plaintext_key = f"{cls.PREFIX}{random_bytes}"
        key_hash = hashlib.sha256(plaintext_key.encode("ascii")).hexdigest()
        key_prefix = plaintext_key[:12]
        return {
            "plaintext_key": plaintext_key,
            "key_hash": key_hash,
            "key_prefix": key_prefix,
            "scopes": scopes,
        }

    @classmethod
    def hash_key(cls, plaintext_key: str) -> str:
        """Hashes plaintext key for secure database comparison."""
        return hashlib.sha256(plaintext_key.encode("ascii")).hexdigest()

    @classmethod
    def validate_scopes(cls, assigned_scopes: List[str], required_scope: str) -> bool:
        """Checks if assigned scopes satisfy the required scope."""
        if "*" in assigned_scopes or "admin" in assigned_scopes:
            return True
        return required_scope in assigned_scopes


class SSRFProtection:
    """
    Enforces strict protocol and destination IP validation on all outbound integrations.
    Blocks private IP subnets, loopbacks, internal hostnames, and cloud metadata endpoints.
    """

    BLOCKED_PATTERNS = [
        re.compile(r"^localhost$", re.I),
        re.compile(r"^127\.\d+\.\d+\.\d+$"),
        re.compile(r"^10\.\d+\.\d+\.\d+$"),
        re.compile(r"^192\.168\.\d+\.\d+$"),
        re.compile(r"^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$"),
        re.compile(r"^169\.254\.\d+\.\d+$"),  # Cloud metadata IP (AWS/GCP/Azure)
        re.compile(r".*\.internal$", re.I),
        re.compile(r".*\.local$", re.I),
    ]

    @classmethod
    def validate_outbound_url(cls, url: str) -> Tuple[bool, Optional[str]]:
        """Validates that a URL is safe for outbound communication."""
        if not url:
            return False, "Target URL cannot be empty."

        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            return False, f"Protocol '{parsed.scheme}' is prohibited. Only HTTPS and HTTP are permitted."

        host = (parsed.hostname or "").lower()
        if not host:
            return False, "URL must contain a valid hostname."

        # Check blocked hostname patterns
        for pattern in cls.BLOCKED_PATTERNS:
            if pattern.match(host):
                return False, f"Outbound access to private/internal host '{host}' is blocked by SSRF defense."

        # Check raw IP address
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local:
                return False, f"Outbound access to private/reserved IP '{host}' is blocked."
        except ValueError:
            pass  # It's a domain name, not a raw IP

        return True, None
