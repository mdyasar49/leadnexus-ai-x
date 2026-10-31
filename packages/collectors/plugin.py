from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.models.discovery import DiscoveryCandidate


class SourcePlugin(ABC):
    """
    Universal Source Plugin Interface:
    Every discovery and collection source (Search, GitHub, Web, Jobs, Forums, RSS)
    implements this unified contract.
    """
    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique key identifier for the source (e.g. 'search_engine', 'github')."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name of the source."""
        pass

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Category type (e.g. 'SEARCH_ENGINE', 'GITHUB', 'JOB_BOARD', 'COMPANY_WEBSITE')."""
        pass

    @abstractmethod
    def discovery(self, campaign_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Discovers new URLs, entities, and preliminary candidate leads."""
        pass

    @abstractmethod
    def fetch(self, url: str) -> Optional[Any]:
        """Performs raw network fetch with rate limiting and timeout."""
        pass

    @abstractmethod
    def browser_fetch(self, url: str) -> Dict[str, Any]:
        """Executes sandboxed browser fetch for dynamic JavaScript pages."""
        pass

    @abstractmethod
    def parse(self, raw_content: Any) -> Dict[str, Any]:
        """Parses raw artifact into structured document tree."""
        pass

    @abstractmethod
    def normalize(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes domains, entity names, dates, and locations."""
        pass

    @abstractmethod
    def extract_entities(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts candidate companies, domains, and organizations."""
        pass

    @abstractmethod
    def extract_signals(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts intent and commercial signals with keyword windows."""
        pass

    @abstractmethod
    def extract_contacts(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extracts publicly listed business emails, phones, and profiles without fabrication."""
        pass

    @abstractmethod
    def extract_evidence(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Builds provenance records with SHA-256 evidence hash and confidence."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Probes source availability and returns latency/status."""
        pass

    @abstractmethod
    def rate_limit_policy(self) -> Dict[str, Any]:
        """Returns rate-limiting constraints (requests/sec, concurrent, daily caps)."""
        pass

    @abstractmethod
    def authentication_requirements(self) -> Dict[str, Any]:
        """Declares required environment API tokens or public credential status."""
        pass

    @abstractmethod
    def robots_policy(self) -> Dict[str, Any]:
        """Returns whether source requires robots.txt compliance checking."""
        pass

    @abstractmethod
    def terms_policy(self) -> Dict[str, Any]:
        """Returns compliance and legal usage constraints."""
        pass

    @abstractmethod
    def supported_regions(self) -> List[str]:
        """List of supported geographies (e.g. ['GLOBAL', 'AU', 'IN', 'US'])."""
        pass

    @abstractmethod
    def supported_content_types(self) -> List[str]:
        """List of supported MIME types (e.g. ['text/html', 'application/json'])."""
        pass

