"""
LeadNexus AI X - Phase 47 Test Suite (ChatGPT Master Roadmap)
Real-Time Streaming Intelligence, Websocket Feeds & Live Signal Broadcast
Tests: BackpressureBuffer, SignalDeduplicator, StreamFilterEngine, SignalAggregator, SignalStreamHub, API routes, and isolation invariants.
"""

import sys
import os
import uuid
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_DIR = os.path.join(BASE_DIR, "apps", "api")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.main import app
from app.db.base import Base
from app.db.session import SessionLocal, sync_engine
from app.models.saved_lead import SavedLead
from packages.streaming.backpressure_buffer import BackpressureBuffer
from packages.streaming.signal_deduplicator import SignalDeduplicator
from packages.streaming.stream_filter_engine import StreamFilterEngine
from packages.streaming.signal_aggregator import SignalAggregator
from packages.streaming.stream_hub import SignalStreamHub


class TestPhase47SignalStreaming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=sync_engine, checkfirst=True)
        cls.db = SessionLocal()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_01_backpressure_buffer_ring_and_overflow(self):
        """Test 1: Verifies bounded ring buffer capacity, FIFO drop-oldest, and drop rate statistics."""
        buf = BackpressureBuffer(capacity=5)
        for i in range(8):
            buf.append({"id": f"item_{i}", "val": i})

        stats = buf.get_stats()
        self.assertEqual(stats["current_size"], 5)
        self.assertEqual(stats["capacity"], 5)
        self.assertEqual(stats["total_appended"], 8)
        self.assertEqual(stats["total_dropped"], 3)
        self.assertAlmostEqual(stats["drop_rate_percent"], 37.5, places=1)

        recent = buf.get_recent(limit=3)
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0]["id"], "item_7")
        self.assertEqual(recent[1]["id"], "item_6")
        self.assertEqual(recent[2]["id"], "item_5")

    def test_02_signal_deduplicator(self):
        """Test 2: Verifies cryptographic signature deduplication suppresses duplicate signals."""
        dedup = SignalDeduplicator(window_seconds=10.0)
        signal = {
            "company_name": "Atlassian",
            "signal_type": "TECH_ADOPTION",
            "topic": "signals.technology",
            "payload": {"tech": "React"},
        }
        self.assertFalse(dedup.is_duplicate(signal))
        # Second time within window must be duplicate
        self.assertTrue(dedup.is_duplicate(signal))

        # Different payload must not be duplicate
        signal_diff = {
            "company_name": "Atlassian",
            "signal_type": "TECH_ADOPTION",
            "topic": "signals.technology",
            "payload": {"tech": "Python"},
        }
        self.assertFalse(dedup.is_duplicate(signal_diff))

    def test_03_stream_filter_engine(self):
        """Test 3: Evaluates equality, containment, and numeric threshold matching."""
        engine = StreamFilterEngine()
        signal = {
            "company_name": "Odoo Australia Pty Ltd",
            "topic": "signals.technology",
            "confidence": 0.96,
            "payload": {"technology": "Odoo ERP", "country": "Australia", "employees": 150},
        }

        # Matching criteria
        self.assertTrue(engine.matches(signal, {"technology": "Odoo", "country": "Australia"}))
        self.assertTrue(engine.matches(signal, {"min_confidence": 0.90}))
        self.assertTrue(engine.matches(signal, {}))

        # Non-matching criteria
        self.assertFalse(engine.matches(signal, {"country": "Germany"}))
        self.assertFalse(engine.matches(signal, {"min_confidence": 0.99}))

    def test_04_signal_aggregator_intent_spike_detection(self):
        """Test 4: Verifies sliding window signal aggregation triggers anomaly alerts upon spike."""
        agg = SignalAggregator(window_seconds=10.0, spike_threshold=3)
        c_name = "Nexus Cloud Solutions"

        alert1 = agg.record_signal({"company_name": c_name})
        self.assertIsNone(alert1)
        alert2 = agg.record_signal({"company_name": c_name})
        self.assertIsNone(alert2)

        # Third signal exceeds threshold
        alert3 = agg.record_signal({"company_name": c_name})
        self.assertIsNotNone(alert3)
        self.assertEqual(alert3["company_name"], c_name)
        self.assertEqual(alert3["signal_count"], 3)
        self.assertIn("surge detected", alert3["description"])

        anomalies = agg.get_recent_anomalies()
        self.assertGreaterEqual(len(anomalies), 1)

    def test_05_stream_hub_publish_and_subscriber_dispatch(self):
        """Test 5: Validates subscription callback dispatching and topic matching."""
        hub = SignalStreamHub(buffer_capacity=100)
        received_signals = []

        sub_id = hub.subscribe(
            topic="signals.hiring",
            filter_criteria={"role": "Engineer"},
            callback=lambda s: received_signals.append(s),
        )
        self.assertIsNotNone(sub_id)

        # Matching signal
        res1 = hub.publish({
            "company_name": "Canva",
            "signal_type": "HIRING_SURGE",
            "topic": "signals.hiring",
            "payload": {"role": "Senior Engineer"},
        })
        self.assertEqual(res1["status"], "PUBLISHED")
        self.assertEqual(res1["dispatched_subscribers"], 1)
        self.assertEqual(len(received_signals), 1)

        # Non-matching signal (different role)
        res2 = hub.publish({
            "company_name": "Canva",
            "signal_type": "HIRING_SURGE",
            "topic": "signals.hiring",
            "payload": {"role": "Product Designer"},
        })
        self.assertEqual(res2["status"], "PUBLISHED")
        self.assertEqual(res2["dispatched_subscribers"], 0)
        self.assertEqual(len(received_signals), 1)

        hub.unsubscribe(sub_id)

    def test_06_stream_hub_recent_queries_with_filters(self):
        """Test 6: Tests querying buffered signals with topic and criteria filtering."""
        hub = SignalStreamHub(buffer_capacity=50)
        hub.publish({"company_name": "Acme", "topic": "signals.tech", "payload": {"tech": "React"}, "confidence": 0.95})
        hub.publish({"company_name": "Beta", "topic": "signals.sales", "payload": {"stage": "Closed"}, "confidence": 0.85})

        tech_signals = hub.get_recent_signals(topic="signals.tech")
        self.assertEqual(len(tech_signals), 1)
        self.assertEqual(tech_signals[0]["company_name"], "Acme")

        high_conf = hub.get_recent_signals(filter_criteria={"min_confidence": 0.90})
        self.assertEqual(len(high_conf), 1)
        self.assertEqual(high_conf[0]["company_name"], "Acme")

    def test_07_stream_hub_stats(self):
        """Test 7: Tests throughput calculations, active topics, and buffer utilization."""
        hub = SignalStreamHub(buffer_capacity=20)
        hub.publish({"company_name": "A", "topic": "t1", "payload": {}})
        hub.publish({"company_name": "B", "topic": "t2", "payload": {}})

        stats = hub.get_stats()
        self.assertEqual(stats["buffered_signals"], 2)
        self.assertEqual(stats["total_signals_published"], 2)
        self.assertIn("t1", stats["active_topics"])
        self.assertIn("t2", stats["active_topics"])
        self.assertGreaterEqual(stats["throughput_signals_per_sec"], 0.0)

    def test_08_api_publish_signal(self):
        """Test 8: Tests POST /api/v1/stream/signals/publish and retrieval."""
        res = self.client.post(
            "/api/v1/stream/signals/publish",
            json={
                "signal_type": "TECH_ADOPTION",
                "company_name": "Xero Limited",
                "topic": "signals.technology",
                "payload": {"framework": "FastAPI", "country": "Australia"},
                "confidence": 0.98,
                "source": "UNIT_TEST",
            },
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["status"], "PUBLISHED")
        self.assertIn("sig_", data["signal_id"])

        # Fetch recent
        res_rec = self.client.get("/api/v1/stream/signals/recent?company=Xero&limit=5")
        self.assertEqual(res_rec.status_code, 200)
        rec_list = res_rec.json()
        self.assertGreaterEqual(len(rec_list), 1)
        self.assertIn("Xero", rec_list[0]["company_name"])

    def test_09_api_subscriptions_lifecycle(self):
        """Test 9: Tests POST, GET, and DELETE /api/v1/stream/subscriptions."""
        res = self.client.post(
            "/api/v1/stream/subscriptions",
            json={
                "topic": "signals.intent.cloud",
                "filter_criteria": {"country": "Australia"},
            },
        )
        self.assertEqual(res.status_code, 201)
        sub = res.json()
        sub_id = sub["id"]
        self.assertTrue(sub["is_active"])

        # List
        res_list = self.client.get("/api/v1/stream/subscriptions")
        self.assertEqual(res_list.status_code, 200)
        subs = res_list.json()
        self.assertTrue(any(s["id"] == sub_id for s in subs))

        # Delete
        res_del = self.client.delete(f"/api/v1/stream/subscriptions/{sub_id}")
        self.assertEqual(res_del.status_code, 200)

    def test_10_api_simulate_surge_and_anomalies(self):
        """Test 10: Tests surge simulator and anomaly retrieval."""
        res_surge = self.client.post(
            "/api/v1/stream/simulate-surge?company_name=TestSurgeCorp&surge_count=4"
        )
        self.assertEqual(res_surge.status_code, 200)
        data = res_surge.json()
        self.assertEqual(data["status"], "SURGE_SIMULATED")
        self.assertEqual(data["signals_emitted"], 4)

        # Retrieve anomalies
        res_anom = self.client.get("/api/v1/stream/anomalies?limit=10")
        self.assertEqual(res_anom.status_code, 200)
        anomalies = res_anom.json()
        self.assertGreater(len(anomalies), 0)
        self.assertTrue(any("TestSurgeCorp" in a["company_name"] for a in anomalies))

    def test_11_streaming_isolation_invariant(self):
        """Test 11: Ensures real-time signal stream operations NEVER mutate saved_leads."""
        initial_saved_count = self.db.query(SavedLead).count()

        # Publish signal
        self.client.post(
            "/api/v1/stream/signals/publish",
            json={
                "signal_type": "BUYING_INTENT",
                "company_name": "InvariantCheckCorp",
                "topic": "signals.intent",
                "payload": {"budget": "$100k"},
                "confidence": 0.99,
            },
        )

        # Simulate surge
        self.client.post("/api/v1/stream/simulate-surge?company_name=InvariantCheckCorp&surge_count=3")

        # Verify saved_leads is strictly unaffected
        final_saved_count = self.db.query(SavedLead).count()
        self.assertEqual(final_saved_count, initial_saved_count)


if __name__ == "__main__":
    unittest.main()
