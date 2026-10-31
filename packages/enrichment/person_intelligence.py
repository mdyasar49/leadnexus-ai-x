from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import re
from sqlalchemy.orm import Session

from app.models.enrichment import (
    PersonRoleObservation,
    PersonRoleChangeEvent,
    RoleChangeType
)


class PersonIntelligenceEngine:
    """Professional person enrichment, role change detection, and collision protection."""

    @staticmethod
    def map_buying_committee_role(title: str) -> str:
        """Assigns buying committee role based on title semantics."""
        if not title:
            return "End User"
        t = title.lower()
        if any(k in t for k in ["ceo", "owner", "founder", "managing director", "vp", "chief", "cfo", "director"]):
            return "Economic Buyer"
        elif any(k in t for k in ["cto", "cio", "architect", "lead engineer", "technical evaluator", "head of it"]):
            return "Technical Evaluator"
        elif any(k in t for k in ["erp", "operations", "project manager", "systems manager", "champion"]):
            return "Champion"
        elif any(k in t for k in ["procurement", "purchasing", "buyer"]):
            return "Procurement"
        elif any(k in t for k in ["implementer", "consultant", "developer"]):
            return "Implementer"
        else:
            return "End User"

    @staticmethod
    def normalize_profile_url(url: str) -> Optional[str]:
        """Normalizes public professional URLs (e.g. LinkedIn, GitHub) removing query tracking parameters."""
        if not url:
            return None
        clean = url.strip()
        # Remove tracking query parameters (?utm_*, ?miniProfileUrn=, etc.)
        if "?" in clean:
            clean = clean.split("?")[0]
        # Remove trailing slash
        clean = clean.rstrip("/")
        return clean.lower()

    @staticmethod
    def match_person_identity(
        candidate: Dict[str, Any],
        existing_people: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], float, str]:
        """
        Matches public person against existing records with Name Collision Protection.
        Rule: Two people with the same name (e.g. 'John Smith') are NEVER merged without
        matching company, domain, or verified profile URL.
        """
        c_name = candidate.get("full_name", "").strip().lower()
        c_company = candidate.get("company_name", "").strip().lower()
        c_url = PersonIntelligenceEngine.normalize_profile_url(candidate.get("profile_url", ""))

        if not c_name:
            return None, 0.0, "MISSING_NAME"

        # Tier 1: Exact Profile URL Match (Strongest unique identifier)
        if c_url:
            for p in existing_people:
                p_url = PersonIntelligenceEngine.normalize_profile_url(p.get("profile_url", ""))
                if p_url and p_url == c_url:
                    return p, 0.99, "EXACT_PROFILE_URL_MATCH"

        # Tier 2: Exact Name + Exact Company Match
        for p in existing_people:
            p_name = p.get("full_name", "").strip().lower()
            p_comp = p.get("company_name", "").strip().lower()
            if p_name == c_name and p_comp and p_comp == c_company:
                return p, 0.95, "NAME_AND_COMPANY_MATCH"

        # Collision Check: Same name, but different company -> Reject merge
        for p in existing_people:
            p_name = p.get("full_name", "").strip().lower()
            p_comp = p.get("company_name", "").strip().lower()
            if p_name == c_name and p_comp and c_company and p_comp != c_company:
                return None, 0.30, "NAME_COLLISION_DIFFERENT_COMPANY_DETECTED"

        return None, 0.90, "NEW_PERSON_CONFIRMED"

    @staticmethod
    def detect_role_change(
        db: Session,
        workspace_id: str,
        person_id: str,
        new_company_name: str,
        new_title: str,
        source_url: str
    ) -> Tuple[Optional[PersonRoleChangeEvent], bool]:
        """
        Detects if a professional changed companies, received a promotion, or changed titles.
        Returns (PersonRoleChangeEvent, has_changed).
        """
        latest_role = (
            db.query(PersonRoleObservation)
            .filter(
                PersonRoleObservation.workspace_id == workspace_id,
                PersonRoleObservation.person_id == person_id,
                PersonRoleObservation.is_current.is_(True)
            )
            .order_by(PersonRoleObservation.observed_at.desc())
            .first()
        )

        now = datetime.now(timezone.utc)
        if not latest_role:
            # First observation of this role
            new_obs = PersonRoleObservation(
                workspace_id=workspace_id,
                person_id=person_id,
                company_id="unknown_or_new",
                company_name=new_company_name,
                title=new_title,
                buying_committee_role=PersonIntelligenceEngine.map_buying_committee_role(new_title),
                is_current=True,
                source_url=source_url,
                confidence=0.90,
                observed_at=now
            )
            db.add(new_obs)
            db.commit()
            return None, False

        # Check for Company Change
        prev_comp = latest_role.company_name.lower().strip()
        curr_comp = new_company_name.lower().strip()
        prev_title = latest_role.title.lower().strip()
        curr_title = new_title.lower().strip()

        change_type = None
        if prev_comp != curr_comp:
            change_type = RoleChangeType.COMPANY_CHANGE.value
        elif prev_title != curr_title:
            if "manager" in curr_title and "manager" not in prev_title:
                change_type = RoleChangeType.PROMOTION.value
            else:
                change_type = RoleChangeType.TITLE_CHANGE.value

        if change_type:
            # Retire previous role
            latest_role.is_current = False
            
            # Record role change event
            event = PersonRoleChangeEvent(
                workspace_id=workspace_id,
                person_id=person_id,
                change_type=change_type,
                previous_role={"company": latest_role.company_name, "title": latest_role.title},
                new_role={"company": new_company_name, "title": new_title},
                detected_at=now,
                source_url=source_url,
                affects_buying_committee=True
            )
            db.add(event)

            # Record new current role
            new_obs = PersonRoleObservation(
                workspace_id=workspace_id,
                person_id=person_id,
                company_id=latest_role.company_id,
                company_name=new_company_name,
                title=new_title,
                buying_committee_role=PersonIntelligenceEngine.map_buying_committee_role(new_title),
                is_current=True,
                source_url=source_url,
                confidence=0.92,
                observed_at=now
            )
            db.add(new_obs)
            db.commit()
            db.refresh(event)
            return event, True

        return None, False
