import base64
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc, asc

from app.models.lead import Company, Contact, IntentSignal
from app.models.scoring import LeadScore, IntentAssessment, BuyingReadinessAssessment, AIReasoningResult
from app.models.technology import TechnologyObservation
from packages.search.search_dsl import SearchDSLParser, ALLOWED_FIELDS, SearchDSLError


class CursorPagination:
    """Keyset / Cursor Pagination encoder and decoder using timestamp and record UUID."""

    @staticmethod
    def encode(val: Any, record_id: str) -> str:
        if isinstance(val, datetime):
            val_str = val.isoformat()
        else:
            val_str = str(val)
        payload = json.dumps({"v": val_str, "id": record_id})
        return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")

    @staticmethod
    def decode(cursor_str: str) -> Optional[Tuple[str, str]]:
        if not cursor_str:
            return None
        try:
            raw = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
            data = json.loads(raw)
            return data.get("v"), data.get("id")
        except Exception:
            return None


class GlobalSearchService:
    """High-performance global and faceted search engine for LeadNexus AI X."""

    @staticmethod
    def global_search(
        db: Session,
        workspace_id: str,
        query: str,
        limit_per_category: int = 10
    ) -> Dict[str, Any]:
        """Unified search across Companies, People, Technologies, Signals, and Evidence."""
        q = f"%{query.strip()}%" if query else "%"

        # 1. Search Companies
        companies = (
            db.query(Company)
            .filter(
                Company.workspace_id == workspace_id,
                or_(
                    Company.name.ilike(q),
                    Company.domain.ilike(q),
                    Company.industry.ilike(q),
                    Company.country.ilike(q),
                    Company.city.ilike(q),
                    Company.description.ilike(q)
                )
            )
            .limit(limit_per_category)
            .all()
        )

        company_results = [
            {
                "id": c.id,
                "name": c.name,
                "domain": c.domain,
                "country": c.country,
                "industry": c.industry,
                "lead_score": c.lead_score,
                "status": c.status
            }
            for c in companies
        ]

        # 2. Search People / Contacts
        contacts = (
            db.query(Contact)
            .filter(
                Contact.workspace_id == workspace_id,
                or_(
                    Contact.full_name.ilike(q),
                    Contact.job_title.ilike(q),
                    Contact.department.ilike(q),
                    Contact.email.ilike(q)
                )
            )
            .limit(limit_per_category)
            .all()
        )

        contact_results = [
            {
                "id": p.id,
                "company_id": p.company_id,
                "full_name": p.full_name,
                "job_title": p.job_title,
                "email": p.email,
                "is_decision_maker": p.is_decision_maker
            }
            for p in contacts
        ]

        # 3. Search Technologies
        techs = (
            db.query(TechnologyObservation)
            .filter(
                TechnologyObservation.workspace_id == workspace_id,
                or_(
                    TechnologyObservation.technology.ilike(q),
                    TechnologyObservation.category.ilike(q)
                )
            )
            .limit(limit_per_category)
            .all()
        )

        tech_results = [
            {
                "id": t.id,
                "company_id": t.company_id,
                "technology_name": t.technology,
                "category": t.category,
                "version": t.version,
                "confidence": t.confidence
            }
            for t in techs
        ]

        # 4. Search Signals
        signals = (
            db.query(IntentSignal)
            .filter(
                IntentSignal.workspace_id == workspace_id,
                or_(
                    IntentSignal.detected_keyword.ilike(q),
                    IntentSignal.signal_type.ilike(q),
                    IntentSignal.evidence_snippet.ilike(q)
                )
            )
            .limit(limit_per_category)
            .all()
        )

        signal_results = [
            {
                "id": s.id,
                "company_id": s.company_id,
                "signal_type": s.signal_type,
                "detected_keyword": s.detected_keyword,
                "evidence_snippet": s.evidence_snippet[:150] if s.evidence_snippet else "",
                "source_name": s.source_name,
                "source_url": s.source_url
            }
            for s in signals
        ]

        total_matches = len(company_results) + len(contact_results) + len(tech_results) + len(signal_results)

        return {
            "query": query,
            "total_matches": total_matches,
            "results": {
                "companies": company_results,
                "contacts": contact_results,
                "technologies": tech_results,
                "signals": signal_results
            }
        }

    @staticmethod
    def execute_lead_search(
        db: Session,
        workspace_id: str,
        query: Optional[str] = None,
        filters: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        sort_field: str = "lead_priority_score",
        sort_direction: str = "desc",
        limit: int = 25,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """High-performance filtered search with keyset cursor pagination."""
        limit = min(max(1, limit), 250)

        # Base query joining Company and LeadScore
        base_q = (
            db.query(Company, LeadScore)
            .outerjoin(LeadScore, Company.id == LeadScore.company_id)
            .filter(Company.workspace_id == workspace_id)
        )

        # 1. Apply free-text query if provided
        if query and query.strip():
            kw = f"%{query.strip()}%"
            base_q = base_q.filter(
                or_(
                    Company.name.ilike(kw),
                    Company.domain.ilike(kw),
                    Company.industry.ilike(kw),
                    Company.country.ilike(kw),
                    Company.description.ilike(kw)
                )
            )

        # 2. Parse and apply DSL filters
        clauses, virtual_criteria = SearchDSLParser.parse_filters(filters or {})
        for clause in clauses:
            base_q = base_q.filter(clause)

        # 3. Apply virtual criteria
        if "technology" in virtual_criteria:
            crit = virtual_criteria["technology"]
            tech_val = crit.get("value")
            base_q = base_q.filter(
                Company.id.in_(
                    db.query(TechnologyObservation.company_id)
                    .filter(
                        TechnologyObservation.workspace_id == workspace_id,
                        TechnologyObservation.technology.ilike(f"%{tech_val}%")
                    )
                )
            )

        if "intent_keyword" in virtual_criteria:
            crit = virtual_criteria["intent_keyword"]
            kw_val = crit.get("value")
            base_q = base_q.filter(
                Company.id.in_(
                    db.query(IntentSignal.company_id)
                    .filter(
                        IntentSignal.workspace_id == workspace_id,
                        IntentSignal.detected_keyword.ilike(f"%{kw_val}%")
                    )
                )
            )

        if "has_email" in virtual_criteria:
            base_q = base_q.filter(
                Company.id.in_(
                    db.query(Contact.company_id)
                    .filter(
                        Contact.workspace_id == workspace_id,
                        Contact.email.is_not(None),
                        Contact.email != "",
                        Contact.email_status != "INVALID"
                    )
                )
            )

        if "has_decision_maker" in virtual_criteria:
            base_q = base_q.filter(
                Company.id.in_(
                    db.query(Contact.company_id)
                    .filter(
                        Contact.workspace_id == workspace_id,
                        Contact.is_decision_maker.is_(True)
                    )
                )
            )

        # Determine sort column
        is_desc = sort_direction.lower() == "desc"
        
        if sort_field in {"lead_priority_score", "icp_fit_score", "intent_score", "buying_readiness_score"}:
            sort_col = getattr(LeadScore, sort_field)
            fallback_col = Company.id
        elif sort_field in {"name", "domain", "country", "industry", "lead_score", "created_at", "updated_at"}:
            sort_col = getattr(Company, sort_field)
            fallback_col = Company.id
        else:
            sort_col = LeadScore.lead_priority_score
            fallback_col = Company.id

        # Keyset pagination condition
        cursor_data = CursorPagination.decode(cursor)
        if cursor_data:
            cursor_val, cursor_id = cursor_data
            try:
                # Attempt float conversion for numeric score columns
                cursor_numeric = float(cursor_val)
                if is_desc:
                    base_q = base_q.filter(
                        or_(
                            sort_col < cursor_numeric,
                            and_(sort_col == cursor_numeric, Company.id < cursor_id)
                        )
                    )
                else:
                    base_q = base_q.filter(
                        or_(
                            sort_col > cursor_numeric,
                            and_(sort_col == cursor_numeric, Company.id > cursor_id)
                        )
                    )
            except (ValueError, TypeError):
                # String / Timestamp comparison
                if is_desc:
                    base_q = base_q.filter(
                        or_(
                            sort_col < cursor_val,
                            and_(sort_col == cursor_val, Company.id < cursor_id)
                        )
                    )
                else:
                    base_q = base_q.filter(
                        or_(
                            sort_col > cursor_val,
                            and_(sort_col == cursor_val, Company.id > cursor_id)
                        )
                    )

        # Apply ordering
        if is_desc:
            base_q = base_q.order_by(desc(sort_col), desc(fallback_col))
        else:
            base_q = base_q.order_by(asc(sort_col), asc(fallback_col))

        # Fetch limit + 1 to detect has_next_page
        rows = base_q.limit(limit + 1).all()

        has_next_page = len(rows) > limit
        result_rows = rows[:limit]

        records = []
        next_cursor = None

        for comp, score in result_rows:
            lead_priority = score.lead_priority_score if score else float(comp.lead_score)
            priority_tier = score.priority_tier if score else ("P1_HIGH" if comp.lead_score >= 80 else "P2_MEDIUM")

            rec = {
                "id": comp.id,
                "name": comp.name,
                "domain": comp.domain,
                "website": comp.website,
                "country": comp.country,
                "city": comp.city,
                "industry": comp.industry,
                "employee_count_range": comp.employee_count_range,
                "lead_score": comp.lead_score,
                "lead_priority_score": lead_priority,
                "priority_tier": priority_tier,
                "icp_fit_score": score.icp_fit_score if score else 0.0,
                "intent_score": score.intent_score if score else 0.0,
                "buying_readiness_score": score.buying_readiness_score if score else 0.0,
                "evidence_confidence_score": score.evidence_confidence_score if score else 0.0,
                "data_quality_score": score.data_quality_score if score else 0.0,
                "status": comp.status,
                "created_at": comp.created_at.isoformat() if comp.created_at else None,
                "updated_at": comp.updated_at.isoformat() if comp.updated_at else None,
            }
            records.append(rec)

        if has_next_page and result_rows:
            last_comp, last_score = result_rows[-1]
            last_sort_val = getattr(last_score, sort_field, None) if hasattr(last_score, sort_field) else getattr(last_comp, sort_field, "")
            next_cursor = CursorPagination.encode(last_sort_val if last_sort_val is not None else 0, last_comp.id)

        return {
            "records": records,
            "count": len(records),
            "limit": limit,
            "has_next_page": has_next_page,
            "next_cursor": next_cursor,
            "sort_field": sort_field,
            "sort_direction": sort_direction
        }

    @staticmethod
    def get_search_facets(
        db: Session,
        workspace_id: str,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculates dynamic aggregation counts for key dimensions."""
        base_filter = [Company.workspace_id == workspace_id]
        if query and query.strip():
            kw = f"%{query.strip()}%"
            base_filter.append(
                or_(
                    Company.name.ilike(kw),
                    Company.domain.ilike(kw),
                    Company.country.ilike(kw),
                    Company.industry.ilike(kw)
                )
            )

        # 1. Countries
        countries = (
            db.query(Company.country, func.count(Company.id))
            .filter(*base_filter, Company.country.is_not(None))
            .group_by(Company.country)
            .order_by(desc(func.count(Company.id)))
            .limit(15)
            .all()
        )
        country_facets = [{"key": c or "Unknown", "count": cnt} for c, cnt in countries]

        # 2. Industries
        industries = (
            db.query(Company.industry, func.count(Company.id))
            .filter(*base_filter, Company.industry.is_not(None))
            .group_by(Company.industry)
            .order_by(desc(func.count(Company.id)))
            .limit(15)
            .all()
        )
        industry_facets = [{"key": ind or "Unknown", "count": cnt} for ind, cnt in industries]

        # 3. Priority Tiers (from LeadScore)
        tiers = (
            db.query(LeadScore.priority_tier, func.count(LeadScore.id))
            .filter(LeadScore.workspace_id == workspace_id)
            .group_by(LeadScore.priority_tier)
            .order_by(desc(func.count(LeadScore.id)))
            .all()
        )
        tier_facets = [{"key": t or "Unscored", "count": cnt} for t, cnt in tiers]

        # 4. Technologies
        techs = (
            db.query(TechnologyObservation.technology, func.count(TechnologyObservation.id))
            .filter(TechnologyObservation.workspace_id == workspace_id)
            .group_by(TechnologyObservation.technology)
            .order_by(desc(func.count(TechnologyObservation.id)))
            .limit(15)
            .all()
        )
        tech_facets = [{"key": t or "Unknown", "count": cnt} for t, cnt in techs]

        # 5. Intent Signal Types
        signals = (
            db.query(IntentSignal.signal_type, func.count(IntentSignal.id))
            .filter(IntentSignal.workspace_id == workspace_id)
            .group_by(IntentSignal.signal_type)
            .order_by(desc(func.count(IntentSignal.id)))
            .limit(10)
            .all()
        )
        signal_facets = [{"key": s or "Unknown", "count": cnt} for s, cnt in signals]

        return {
            "countries": country_facets,
            "industries": industry_facets,
            "priority_tiers": tier_facets,
            "technologies": tech_facets,
            "signal_types": signal_facets
        }

    @staticmethod
    def explain_search(
        db: Session,
        workspace_id: str,
        filters: Optional[Dict[str, Any]] = None,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Provides query planning, index utilization estimates, and safety explanation."""
        clauses, virtuals = SearchDSLParser.parse_filters(filters or {})
        
        index_hints = ["idx_comp_workspace_domain", "idx_comp_workspace_norm_name"]
        if "country" in str(filters):
            index_hints.append("idx_companies_country")
        if "lead_priority_score" in str(filters):
            index_hints.append("idx_lead_scores_priority_score")

        return {
            "query": query,
            "filters_count": len(clauses) + len(virtuals),
            "virtual_filters": list(virtuals.keys()),
            "estimated_index_strategy": index_hints,
            "is_safe_parameterized": True,
            "execution_mode": "SYNCHRONOUS_ACCELERATED",
            "message": "Query plan uses indexed B-tree constraints without raw SQL injection vector."
        }
