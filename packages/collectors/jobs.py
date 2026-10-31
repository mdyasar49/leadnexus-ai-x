import logging
from typing import Dict, Any, Generator, List, Optional
from packages.collectors.base import BaseCollector
from packages.collectors.signal_extractor import RawSignal, extract_evidence_snippet

logger = logging.getLogger("leadnexus.collectors.jobs")


class JobsCollector(BaseCollector):
    """
    Enterprise Job Board & Career Intent Collector:
    - Scrapes public career feeds and open job search APIs (e.g., RemoteOK public API, public board aggregators)
    - Detects explicit hiring intent for target enterprise tools (Odoo, Zoho, Salesforce, SAP)
    - Deep pagination across job search listings without artificial caps
    - Identifies employer company names, job titles, location, and requirement snippets
    """
    def __init__(self):
        super().__init__(name="job_boards", default_delay=0.6, timeout=15)
        self.remoteok_api = "https://remoteok.com/api"

    def collect_stream(
        self,
        campaign_config: Dict[str, Any]
    ) -> Generator[RawSignal, None, None]:
        """
        Continuously streams hiring intent signals from public job aggregators.
        """
        intent_keywords = campaign_config.get("intent_keywords", [])
        company_keywords = campaign_config.get("company_keywords", [])
        target_country = campaign_config.get("country", "")

        tags = list(set([k.lower().replace(" ", "-") for k in (company_keywords or ["odoo", "erp", "zoho"])]))
        
        logger.info(f"[Jobs Collector] Querying job feeds for tags: {tags}")

        # Fetch public RemoteOK feed
        resp = self.fetch_url(
            self.remoteok_api,
            headers={"User-Agent": "LeadNexusAI-JobsResearcher/1.0"}
        )
        if resp and resp.status_code == 200:
            try:
                jobs = resp.json()
                if isinstance(jobs, list):
                    # First item in remoteok API is metadata
                    for job in jobs[1:]:
                        if not isinstance(job, dict):
                            continue
                        
                        position = job.get("position", "")
                        company = job.get("company", "")
                        description = job.get("description", "")
                        url = job.get("url") or f"https://remoteok.com/remote-jobs/{job.get('id', '')}"
                        location = job.get("location", "")
                        job_tags = [t.lower() for t in job.get("tags", [])]

                        # Check if any target keyword matches position, tags, or description
                        full_content = f"{position} at {company} - {' '.join(job_tags)} {description}"
                        
                        for kw in (intent_keywords + company_keywords + ["Odoo", "ERP", "Zoho"]):
                            if kw.lower() in full_content.lower():
                                evidence = extract_evidence_snippet(full_content, kw, window=140)
                                signal = RawSignal(
                                    source_name="job_boards",
                                    source_url=url,
                                    detected_keyword=kw,
                                    evidence_snippet=evidence,
                                    signal_type="HIRING_INTENT_SIGNAL",
                                    signal_strength=1.8,  # Hiring has very strong commercial intent
                                    company_name_hint=company,
                                    location_hint=location,
                                    raw_payload={
                                        "position": position,
                                        "company": company,
                                        "date": job.get("date"),
                                        "tags": job_tags,
                                    }
                                )
                                yield signal
            except Exception as e:
                logger.error(f"[Jobs Collector] Error parsing jobs payload: {e}")

