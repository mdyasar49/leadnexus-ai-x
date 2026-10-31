import re
import hashlib
from typing import Dict, Any, List
from app.models.technology import TechnologyCategory

TECH_CATALOG = [
    # ERP
    ("Odoo", TechnologyCategory.ERP, [r'\bodoo\b']),
    ("Microsoft Dynamics", TechnologyCategory.ERP, [r'\bmicrosoft dynamics\b', r'\bdynamics 365\b', r'\bnavision\b']),
    ("SAP", TechnologyCategory.ERP, [r'\bsap s/4hana\b', r'\bsap business one\b', r'\bsap ecc\b']),
    ("NetSuite", TechnologyCategory.ERP, [r'\bnetsuite\b', r'\boracle netsuite\b']),
    # CRM
    ("Zoho", TechnologyCategory.CRM, [r'\bzoho\b', r'\bzoho crm\b', r'\bzoho one\b']),
    ("Salesforce", TechnologyCategory.CRM, [r'\bsalesforce\b', r'\bsfdc\b']),
    ("HubSpot", TechnologyCategory.CRM, [r'\bhubspot\b']),
    # E-commerce
    ("Shopify", TechnologyCategory.ECOMMERCE, [r'\bshopify\b', r'\bcdn\.shopify\.com\b']),
    ("WooCommerce", TechnologyCategory.ECOMMERCE, [r'\bwoocommerce\b']),
    ("Magento", TechnologyCategory.ECOMMERCE, [r'\bmagento\b', r'\badobe commerce\b']),
    ("BigCommerce", TechnologyCategory.ECOMMERCE, [r'\bbigcommerce\b']),
    # Cloud
    ("AWS", TechnologyCategory.CLOUD_HOSTING, [r'\bamazon web services\b', r'\baws\b']),
    ("Azure", TechnologyCategory.CLOUD_HOSTING, [r'\bmicrosoft azure\b', r'\bazure\b']),
    ("Google Cloud", TechnologyCategory.CLOUD_HOSTING, [r'\bgoogle cloud\b', r'\bgcp\b']),
    # Frontend / Frameworks
    ("React", TechnologyCategory.FRONTEND_FRAMEWORK, [r'\breact(?:js)?\b']),
    ("Next.js", TechnologyCategory.FRONTEND_FRAMEWORK, [r'\bnext\.js\b', r'\b__next\b']),
    ("WordPress", TechnologyCategory.FRONTEND_FRAMEWORK, [r'\bwordpress\b', r'\bwp-content\b']),
    # Backend & DB
    ("Python", TechnologyCategory.BACKEND_FRAMEWORK, [r'\bpython\b']),
    ("FastAPI", TechnologyCategory.BACKEND_FRAMEWORK, [r'\bfastapi\b']),
    ("Django", TechnologyCategory.BACKEND_FRAMEWORK, [r'\bdjango\b']),
    ("PostgreSQL", TechnologyCategory.DATABASE, [r'\bpostgresql\b', r'\bpostgres\b']),
    ("MySQL", TechnologyCategory.DATABASE, [r'\bmysql\b']),
]


class TechnologyIntelligence:
    """
    Enterprise Technology Stack Analyzer:
    - Identifies technology platforms, frameworks, and infrastructure footprints
    - Requires evidence grounding to avoid false positives
    """
    @classmethod
    def detect_technologies(cls, text: str, source_url: str) -> List[Dict[str, Any]]:
        if not text:
            return []

        observations = []
        clean_text = " ".join(text.split())

        for tech_name, category, regexes in TECH_CATALOG:
            for pattern_str in regexes:
                match = re.search(pattern_str, clean_text, re.IGNORECASE)
                if match:
                    start = max(0, match.start() - 50)
                    end = min(len(clean_text), match.end() + 50)
                    evidence = clean_text[start:end]
                    evidence_hash = hashlib.sha256(f"{source_url}:{tech_name}:{evidence}".encode("utf-8")).hexdigest()

                    observations.append({
                        "technology": tech_name,
                        "category": category.value,
                        "source_url": source_url,
                        "evidence_text": evidence,
                        "evidence_hash": evidence_hash,
                        "confidence": 0.92,
                        "detection_method": "REGEX_PATTERN_MATCH",
                    })
                    break  # One match per technology is sufficient

        return observations

