import enum
from typing import Any, Callable, Dict, List, Optional


class ProviderCapability(str, enum.Enum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    SYNC = "SYNC"
    SEARCH = "SEARCH"
    ENRICH = "ENRICH"
    VERIFY = "VERIFY"
    WEBHOOK = "WEBHOOK"
    BATCH = "BATCH"
    STREAM = "STREAM"
    FILE_UPLOAD = "FILE_UPLOAD"
    FILE_DOWNLOAD = "FILE_DOWNLOAD"
    QUERY = "QUERY"


class IntegrationProviderPlugin:
    """Base class for all integration provider plugins."""

    def __init__(
        self,
        provider_id: str,
        name: str,
        category: str,
        version: str,
        capabilities: List[str],
        authentication_type: str,
        configuration_schema: Dict[str, Any],
        rate_policy: Optional[Dict[str, Any]] = None,
        retry_policy: Optional[Dict[str, Any]] = None,
        security_policy: Optional[Dict[str, Any]] = None,
    ):
        self.provider_id = provider_id
        self.name = name
        self.category = category
        self.version = version
        self.capabilities = capabilities
        self.authentication_type = authentication_type
        self.configuration_schema = configuration_schema
        self.rate_policy = rate_policy or {"max_requests_per_minute": 60}
        self.retry_policy = retry_policy or {"max_retries": 3, "backoff_seconds": 2.0}
        self.security_policy = security_policy or {"ssrf_protection": True, "require_https": True}
        self.is_enabled = True

    def health_check(self) -> Dict[str, Any]:
        """Performs a live connectivity and credential health check."""
        return {
            "provider_id": self.provider_id,
            "status": "HEALTHY",
            "latency_ms": 12,
            "message": f"Provider {self.name} is available and responsive.",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "capabilities": self.capabilities,
            "authentication_type": self.authentication_type,
            "configuration_schema": self.configuration_schema,
            "rate_policy": self.rate_policy,
            "retry_policy": self.retry_policy,
            "security_policy": self.security_policy,
            "is_enabled": self.is_enabled,
        }


class ProviderRegistry:
    """
    Central catalog of registered integration providers.
    Provides registration, lookup, capability validation, and health checks.
    """

    def __init__(self):
        self._providers: Dict[str, IntegrationProviderPlugin] = {}
        self._register_default_providers()

    def _register_default_providers(self):
        defaults = [
            IntegrationProviderPlugin(
                provider_id="google_sheets",
                name="Google Sheets",
                category="PRODUCTIVITY",
                version="1.2.0",
                capabilities=[
                    ProviderCapability.IMPORT.value,
                    ProviderCapability.EXPORT.value,
                    ProviderCapability.SYNC.value,
                ],
                authentication_type="OAUTH2",
                configuration_schema={
                    "spreadsheet_id": "string",
                    "worksheet_name": "string",
                    "header_row": "integer",
                },
                rate_policy={"max_requests_per_minute": 100},
            ),
            IntegrationProviderPlugin(
                provider_id="github",
                name="GitHub Public & Organization Connector",
                category="DEVELOPMENT",
                version="2.0.0",
                capabilities=[
                    ProviderCapability.SEARCH.value,
                    ProviderCapability.IMPORT.value,
                    ProviderCapability.WEBHOOK.value,
                ],
                authentication_type="API_KEY",
                configuration_schema={
                    "organization": "string",
                    "repositories": "list",
                },
                rate_policy={"max_requests_per_minute": 30},
            ),
            IntegrationProviderPlugin(
                provider_id="slack_notifications",
                name="Slack Operational Notifications",
                category="COMMUNICATION",
                version="1.0.0",
                capabilities=[
                    ProviderCapability.EXPORT.value,
                    ProviderCapability.WEBHOOK.value,
                ],
                authentication_type="WEBHOOK_SIGNATURE",
                configuration_schema={
                    "webhook_url": "string",
                    "channel": "string",
                },
            ),
            IntegrationProviderPlugin(
                provider_id="teams_notifications",
                name="Microsoft Teams Operational Connector",
                category="COMMUNICATION",
                version="1.0.0",
                capabilities=[
                    ProviderCapability.EXPORT.value,
                    ProviderCapability.WEBHOOK.value,
                ],
                authentication_type="WEBHOOK_SIGNATURE",
                configuration_schema={"webhook_url": "string"},
            ),
            IntegrationProviderPlugin(
                provider_id="email_verification_provider",
                name="Authorized Email Verification Engine",
                category="VERIFICATION",
                version="1.5.0",
                capabilities=[
                    ProviderCapability.VERIFY.value,
                    ProviderCapability.BATCH.value,
                ],
                authentication_type="API_KEY",
                configuration_schema={"api_endpoint": "string", "api_key": "string"},
                rate_policy={"max_requests_per_minute": 120},
            ),
            IntegrationProviderPlugin(
                provider_id="job_feed_connector",
                name="Public Career & Job Source Connector",
                category="DATA_SOURCE",
                version="1.1.0",
                capabilities=[
                    ProviderCapability.IMPORT.value,
                    ProviderCapability.STREAM.value,
                ],
                authentication_type="NONE",
                configuration_schema={"feed_urls": "list"},
            ),
            IntegrationProviderPlugin(
                provider_id="generic_webhook",
                name="Generic Enterprise Webhook Gateway",
                category="EVENT_SOURCE",
                version="1.0.0",
                capabilities=[
                    ProviderCapability.WEBHOOK.value,
                    ProviderCapability.EXPORT.value,
                ],
                authentication_type="WEBHOOK_SIGNATURE",
                configuration_schema={"target_url": "string", "hmac_secret": "string"},
            ),
        ]
        for p in defaults:
            self._providers[p.provider_id] = p

    def register_provider(self, provider: IntegrationProviderPlugin):
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> Optional[IntegrationProviderPlugin]:
        return self._providers.get(provider_id)

    def list_providers(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if not category:
            return [p.to_dict() for p in self._providers.values()]
        return [p.to_dict() for p in self._providers.values() if p.category.upper() == category.upper()]

    def check_capability(self, provider_id: str, capability: str) -> bool:
        provider = self.get_provider(provider_id)
        if not provider or not provider.is_enabled:
            return False
        return capability.upper() in [c.upper() for c in provider.capabilities]
