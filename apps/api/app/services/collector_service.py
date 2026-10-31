import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.run import ResearchRun, ResearchJob, RunStatus, JobStatus
from app.models.campaign import Campaign
from app.models.lead import IntentSignal
from packages.collectors.github import GitHubCollector
from packages.collectors.website import WebsiteCollector
from packages.collectors.rss import RSSCollector
from packages.collectors.jobs import JobsCollector
from packages.collectors.base import BaseCollector

logger = logging.getLogger("leadnexus.services.collector")


class CollectorService:
    """
    Orchestrates distributed, multi-source signal collection for Research Runs.
    Supports continuous unlimited data harvesting across all enabled channels.
    """
    def __init__(self, db: Session):
        self.db = db
        self.registry: Dict[str, BaseCollector] = {
            "github": GitHubCollector(),
            "company_website": WebsiteCollector(),
            "rss_feeds": RSSCollector(),
            "job_boards": JobsCollector(),
        }

    def execute_collection_for_run(
        self,
        run_id: str,
        limit_override: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes discovery collection for a run.
        If campaign limit is 0 or limit_override is 0/None, executes in UNLIMITED mode.
        """
        run = self.db.query(ResearchRun).filter(ResearchRun.id == run_id).first()
        if not run:
            raise ValueError(f"Research run not found: {run_id}")

        campaign = self.db.query(Campaign).filter(Campaign.id == run.campaign_id).first()
        if not campaign:
            raise ValueError(f"Campaign not found for run: {run_id}")

        cfg_model = campaign.config
        campaign_config = {
            "campaign_name": campaign.name,
            "intent_keywords": cfg_model.intent_keywords if cfg_model else [],
            "company_keywords": cfg_model.company_keywords if cfg_model else [],
            "country": cfg_model.country if cfg_model else "",
            "target_job_titles": cfg_model.target_job_titles if cfg_model else [],
            "maximum_results": cfg_model.maximum_results if cfg_model else 0,
        }

        # Determine limit: 0 or None means UNLIMITED
        configured_max = campaign_config.get("maximum_results", 100)
        target_limit = limit_override if limit_override is not None else configured_max
        is_unlimited = (target_limit is None or target_limit <= 0)

        logger.info(
            f"[Collector Service] Starting collection for run {run_id}. "
            f"Mode: {'UNLIMITED' if is_unlimited else f'Limit={target_limit}'}"
        )

        total_collected = 0
        source_counts: Dict[str, int] = {}

        # Query pending or queued jobs for this run
        jobs = self.db.query(ResearchJob).filter(
            ResearchJob.run_id == run_id,
            ResearchJob.stage == "DISCOVERY"
        ).all()

        active_jobs = jobs if jobs else []

        for source_key, collector in self.registry.items():
            if not is_unlimited and total_collected >= target_limit:
                break

            logger.info(f"[Collector Service] Launching collector '{source_key}'...")
            
            # Find or create corresponding job
            job = next((j for j in active_jobs if j.source_key == source_key), None)
            if job:
                job.status = JobStatus.RUNNING

            collected_for_source = 0
            try:
                per_source_limit = None if is_unlimited else max(10, (target_limit - total_collected))
                
                # Stream signals
                for raw_signal in collector.collect_stream(campaign_config):
                    # Persist intent signal to database
                    db_signal = IntentSignal(
                        workspace_id=run.workspace_id,
                        campaign_id=campaign.id,
                        run_id=run.id,
                        source_name=raw_signal.source_name,
                        source_url=raw_signal.source_url,
                        signal_type=raw_signal.signal_type,
                        detected_keyword=raw_signal.detected_keyword,
                        raw_content=raw_signal.evidence_snippet,
                        evidence_snippet=raw_signal.evidence_snippet,
                        signal_strength=raw_signal.signal_strength,
                        raw_data=raw_signal.to_dict()
                    )
                    self.db.add(db_signal)
                    collected_for_source += 1
                    total_collected += 1

                    if not is_unlimited and total_collected >= target_limit:
                        break
                    
                    # Periodic commit every 25 items for safe persistence
                    if collected_for_source % 25 == 0:
                        self.db.commit()

                self.db.commit()
                if job:
                    job.status = JobStatus.COMPLETED
                    job.items_found = collected_for_source
                    job.items_processed = collected_for_source
            except Exception as e:
                logger.error(f"[Collector Service] Error in source '{source_key}': {e}", exc_info=True)
                if job:
                    job.status = JobStatus.FAILED
                    job.last_error = str(e)
                    job.error_count += 1
                self.db.rollback()

            source_counts[source_key] = collected_for_source

        # Update run stats
        run.total_companies_found = total_collected
        run.stats = {
            "signals_collected": total_collected,
            "by_source": source_counts,
            "mode": "unlimited" if is_unlimited else "capped"
        }
        self.db.commit()

        logger.info(f"[Collector Service] Collection completed for run {run_id}. Total signals: {total_collected}")
        return {
            "run_id": run_id,
            "total_signals": total_collected,
            "by_source": source_counts,
            "mode": "unlimited" if is_unlimited else "capped"
        }
