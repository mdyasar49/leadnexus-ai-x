import unittest
import os
import sys
import uuid
from unittest.mock import patch, MagicMock

# Add apps/api and monorepo root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.db.session import SessionLocal, init_sync_db
from app.models.tenant import Organization, Workspace
from app.models.campaign import Campaign, CampaignConfig, CampaignStatus
from app.models.run import ResearchRun, ResearchJob, RunStatus, JobStatus
from app.models.lead import IntentSignal
from packages.collectors.base import BaseCollector
from packages.collectors.signal_extractor import RawSignal, extract_evidence_snippet
from packages.collectors.github import GitHubCollector
from packages.collectors.website import WebsiteCollector
from packages.collectors.rss import RSSCollector
from packages.collectors.jobs import JobsCollector
from app.services.collector_service import CollectorService


class CollectorsTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_sync_db()
        cls.db = SessionLocal()

        # Create test workspace and campaign
        cls.org = Organization(name="Test Discovery Org", slug=f"test-disc-{uuid.uuid4().hex[:6]}")
        cls.db.add(cls.org)
        cls.db.flush()

        cls.ws = Workspace(name="Test Discovery WS", slug=f"test-ws-{uuid.uuid4().hex[:6]}", organization_id=cls.org.id)
        cls.db.add(cls.ws)
        cls.db.flush()

        cls.campaign = Campaign(
            name="Unlimited Odoo Discovery",
            workspace_id=cls.ws.id,
            organization_id=cls.org.id,
            status=CampaignStatus.ACTIVE,
        )
        cls.db.add(cls.campaign)
        cls.db.flush()

        cls.config = CampaignConfig(
            campaign_id=cls.campaign.id,
            country="Australia",
            intent_keywords=["Odoo", "Odoo migration", "ERP integration"],
            company_keywords=["Odoo", "ERP"],
            target_job_titles=["IT Manager", "CTO"],
            maximum_results=0,  # UNLIMITED MODE
        )
        cls.db.add(cls.config)
        cls.db.commit()

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_evidence_snippet_extraction(self):
        text = "Our enterprise retail business is actively looking for an Odoo migration partner to modernize POS systems."
        snippet = extract_evidence_snippet(text, "Odoo migration", window=30)
        self.assertIn("Odoo migration", snippet)
        self.assertTrue(snippet.startswith("..."))
        self.assertTrue(snippet.endswith("..."))

        # Empty/None handling
        self.assertEqual(extract_evidence_snippet("", "keyword"), "")

    def test_02_raw_signal_serialization(self):
        sig = RawSignal(
            source_name="github",
            source_url="https://github.com/example/issue/1",
            detected_keyword="Odoo migration",
            evidence_snippet="...seeking Odoo migration...",
            signal_type="GITHUB_ISSUE",
            signal_strength=1.5,
            author_or_speaker="dev_lead",
            company_name_hint="Acme Retail",
            domain_hint="acmeretail.com.au"
        )
        data = sig.to_dict()
        self.assertEqual(data["source_name"], "github")
        self.assertEqual(data["detected_keyword"], "Odoo migration")
        self.assertEqual(data["company_name_hint"], "Acme Retail")
        self.assertIn("captured_at", data)

    def test_03_base_collector_robots_and_backoff(self):
        collector = BaseCollector(name="test_bot", default_delay=0.01)
        self.assertEqual(collector.name, "test_bot")
        
        # Test robots.txt check fallback on unreachable domain
        allowed = collector.is_allowed_by_robots("http://non-existent-domain-test.local/page")
        self.assertTrue(allowed)

    @patch.object(GitHubCollector, "get_user_or_org_details")
    @patch.object(GitHubCollector, "fetch_url")
    def test_04_github_collector_deep_pagination(self, mock_fetch, mock_user):
        mock_user.return_value = {
            "name": "Acme Lead",
            "company": "Acme Australia",
            "blog": "acme.com.au",
            "location": "Sydney, Australia"
        }

        # Mock 2 pages of GitHub API search responses
        mock_resp_p1 = MagicMock()
        mock_resp_p1.status_code = 200
        mock_resp_p1.headers = {"X-RateLimit-Remaining": "50"}
        mock_resp_p1.json.return_value = {
            "items": [
                {
                    "id": 101,
                    "title": "Need Odoo migration help",
                    "body": "We are migrating to Odoo 17 and need an implementation partner in Australia.",
                    "html_url": "https://github.com/acme/odoo-erp/issues/101",
                    "user": {"login": "acme_lead"}
                }
            ]
        }

        mock_resp_p2 = MagicMock()
        mock_resp_p2.status_code = 200
        mock_resp_p2.headers = {"X-RateLimit-Remaining": "49"}
        mock_resp_p2.json.return_value = {
            "items": [
                {
                    "id": 102,
                    "title": "ERP integration bug",
                    "body": "Having issues with ERP integration between Shopify and custom modules.",
                    "html_url": "https://github.com/retail/shop/issues/102",
                    "user": {"login": "retail_dev"}
                }
            ]
        }

        # Page 3 empty stops pagination
        mock_resp_empty = MagicMock()
        mock_resp_empty.status_code = 200
        mock_resp_empty.headers = {"X-RateLimit-Remaining": "48"}
        mock_resp_empty.json.return_value = {"items": []}

        mock_fetch.side_effect = [mock_resp_p1, mock_resp_p2, mock_resp_empty, mock_resp_empty, mock_resp_empty, mock_resp_empty]

        gh = GitHubCollector()
        campaign_cfg = {"intent_keywords": ["Odoo migration", "ERP integration"]}
        
        # Test unlimited stream collection
        signals = []
        for s in gh.collect_stream(campaign_cfg):
            signals.append(s)
            if len(signals) >= 2:
                break

        self.assertGreaterEqual(len(signals), 2)
        self.assertEqual(signals[0].source_name, "github")
        self.assertIn("Odoo", signals[0].evidence_snippet)

    def test_05_rss_feed_parsing(self):
        rss = RSSCollector()
        sample_xml = b"""<?xml version="1.0" encoding="UTF-8" ?>
        <rss version="2.0">
        <channel>
            <title>Enterprise Tech News</title>
            <item>
                <title>Australian Retailer Initiates Major Odoo ERP Migration</title>
                <link>https://technews.com/odoo-migration-case</link>
                <description>A prominent Sydney retailer announced a full ERP integration with Odoo systems.</description>
                <pubDate>Mon, 31 Oct 2026 10:00:00 GMT</pubDate>
            </item>
        </channel>
        </rss>"""
        entries = rss._parse_xml_feed(sample_xml)
        self.assertEqual(len(entries), 1)
        self.assertIn("Odoo ERP Migration", entries[0]["title"])
        self.assertEqual(entries[0]["link"], "https://technews.com/odoo-migration-case")

    @patch.object(JobsCollector, "fetch_url")
    def test_06_jobs_collector_hiring_intent(self, mock_fetch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {"legal": "metadata header"},
            {
                "id": "job_998",
                "position": "Senior Odoo ERP Developer",
                "company": "Pacific Logistics Pty Ltd",
                "description": "Looking for an expert in Odoo migration and custom module development in Sydney.",
                "url": "https://remoteok.com/remote-jobs/job_998",
                "location": "Australia",
                "tags": ["odoo", "python", "erp"]
            }
        ]
        mock_fetch.return_value = mock_resp

        jobs_collector = JobsCollector()
        campaign_cfg = {"company_keywords": ["Odoo"], "intent_keywords": ["migration"]}
        
        signals = []
        for s in jobs_collector.collect_stream(campaign_cfg):
            signals.append(s)
            break

        self.assertEqual(len(signals), 1)
        sig = signals[0]
        self.assertEqual(sig.source_name, "job_boards")
        self.assertEqual(sig.company_name_hint, "Pacific Logistics Pty Ltd")
        self.assertEqual(sig.signal_strength, 1.8)

    def test_07_collector_service_unlimited_execution(self):
        # Create a run in DB
        run = ResearchRun(
            campaign_id=self.campaign.id,
            workspace_id=self.ws.id,
            status=RunStatus.RUNNING,
            trigger_type="test"
        )
        self.db.add(run)
        self.db.commit()

        # Mock collectors in service to yield controlled signals
        svc = CollectorService(self.db)
        
        mock_gh = MagicMock()
        mock_gh.collect_stream.return_value = iter([
            RawSignal("github", "https://github.com/test/1", "Odoo", "evidence 1"),
            RawSignal("github", "https://github.com/test/2", "Odoo", "evidence 2"),
        ])
        mock_jobs = MagicMock()
        mock_jobs.collect_stream.return_value = iter([
            RawSignal("job_boards", "https://jobs.com/test/1", "ERP", "evidence jobs", company_name_hint="Pacific Retail")
        ])

        svc.registry["github"] = mock_gh
        svc.registry["job_boards"] = mock_jobs
        svc.registry["company_website"].collect_stream = MagicMock(return_value=iter([]))
        svc.registry["rss_feeds"].collect_stream = MagicMock(return_value=iter([]))

        # Execute in unlimited mode (limit_override=0)
        res = svc.execute_collection_for_run(run.id, limit_override=0)
        
        self.assertEqual(res["mode"], "unlimited")
        self.assertEqual(res["total_signals"], 3)
        self.assertEqual(res["by_source"]["github"], 2)
        self.assertEqual(res["by_source"]["job_boards"], 1)

        # Verify DB persistence of signals
        db_signals = self.db.query(IntentSignal).filter(IntentSignal.run_id == run.id).all()
        self.assertEqual(len(db_signals), 3)
        self.assertTrue(all(s.evidence_snippet != "" for s in db_signals))


if __name__ == "__main__":
    unittest.main()
