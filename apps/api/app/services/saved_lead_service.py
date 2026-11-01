"""
LeadNexus AI X — Saved Leads Service
Phase 9, 10 & 11: Explicit Save, Duplicate Prevention & Saved Leads Management
CRITICAL BUSINESS RULE: Only leads explicitly added by the user are saved and exported.
Temporary search results must never be included in the Saved Leads page or exports.
"""

import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from app.models.lead import Company, Contact
from app.models.saved_lead import SavedLead


class DuplicateLeadError(Exception):
    """Raised when an attempt is made to save an already saved lead."""
    pass


class SavedLeadService:
    """
    Manages user-selected saved leads with strict duplicate prevention and relational integrity.
    """

    @classmethod
    def save_lead(
        cls,
        db: Session,
        company_id: str,
        contact_id: Optional[str] = None,
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
        evidence: Optional[str] = None,
        search_keyword: Optional[str] = None,
    ) -> Tuple[SavedLead, bool]:
        """
        Saves a lead into the saved_leads table.
        Returns: (saved_lead, is_new)
        If duplicate already exists, returns (existing_lead, False).
        """
        # 1. Validate Company
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            raise ValueError(f"Company with ID '{company_id}' does not exist.")

        # 2. Validate Contact if supplied
        if contact_id:
            contact = db.query(Contact).filter(Contact.id == contact_id).first()
            if not contact:
                contact_id = None  # fallback to company-only saved lead

        # 3. Check for duplicates
        existing_query = db.query(SavedLead).filter(SavedLead.company_id == company_id)
        if contact_id:
            existing_query = existing_query.filter(SavedLead.contact_id == contact_id)
        else:
            existing_query = existing_query.filter(SavedLead.contact_id.is_(None))

        existing = existing_query.first()
        if existing:
            # Duplicate prevention: return existing record without duplicate insertion
            return existing, False

        # 4. Insert into saved_leads
        saved = SavedLead(
            id=str(uuid.uuid4()),
            company_id=company_id,
            contact_id=contact_id,
            source_name=source_name or "LeadNexus Intelligence",
            source_url=source_url or company.website or "https://abr.business.gov.au",
            evidence=evidence or "Verified business record added to saved leads.",
            search_keyword=search_keyword or "B2B Lead",
            saved_at=datetime.now(timezone.utc),
        )
        db.add(saved)
        db.commit()
        db.refresh(saved)
        return saved, True

    @classmethod
    def list_saved_leads(
        cls,
        db: Session,
        search: Optional[str] = None,
        company: Optional[str] = None,
        location: Optional[str] = None,
        industry: Optional[str] = None,
        job_title: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieves ONLY records explicitly saved in the saved_leads table.
        Temporary search results must NEVER appear here.
        """
        query = (
            db.query(SavedLead, Company, Contact)
            .join(Company, SavedLead.company_id == Company.id)
            .outerjoin(Contact, SavedLead.contact_id == Contact.id)
        )

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Company.name.ilike(search_pattern),
                    Company.industry.ilike(search_pattern),
                    Company.city.ilike(search_pattern),
                    Company.country.ilike(search_pattern),
                    Contact.full_name.ilike(search_pattern),
                    Contact.job_title.ilike(search_pattern),
                    SavedLead.search_keyword.ilike(search_pattern),
                )
            )

        if company:
            query = query.filter(Company.name.ilike(f"%{company.strip()}%"))
        if location:
            loc_pat = f"%{location.strip()}%"
            query = query.filter(or_(Company.country.ilike(loc_pat), Company.city.ilike(loc_pat), Company.state.ilike(loc_pat)))
        if industry:
            query = query.filter(Company.industry.ilike(f"%{industry.strip()}%"))
        if job_title:
            query = query.filter(Contact.job_title.ilike(f"%{job_title.strip()}%"))

        total_count = query.count()
        rows = query.order_by(desc(SavedLead.saved_at)).offset(offset).limit(limit).all()

        items = []
        for saved, comp, cont in rows:
            items.append({
                "id": saved.id,
                "saved_at": saved.saved_at.strftime("%Y-%m-%d %H:%M:%S") if saved.saved_at else None,
                "search_keyword": saved.search_keyword or "Not Specified",
                "source_name": saved.source_name or "Public Registry",
                "source_url": saved.source_url or "Not Found",
                "evidence": saved.evidence or "Not Found",
                
                # Company Details
                "company_id": comp.id,
                "company_name": comp.name,
                "website": comp.website or (f"https://www.{comp.domain}" if comp.domain else None) or "Not Found",
                "industry": comp.industry or "Not Found",
                "country": comp.country or "Australia",
                "state": comp.state or "Not Found",
                "city": comp.city or "Not Found",
                "description": comp.description or "Not Found",
                
                # Contact Details
                "contact_id": cont.id if cont else None,
                "decision_maker_name": cont.full_name if cont else "Not Found",
                "job_title": cont.job_title if cont else "Not Found",
                "business_email": cont.email if cont else "Not Found",
                "email_status": cont.email_status if cont else "NOT_FOUND",
                "business_phone": cont.business_phone if cont else "Not Found",
                "phone_status": cont.phone_status if cont else "NOT_FOUND",
                "linkedin_url": cont.profile_url if cont else "Not Found",
            })

        return items, total_count

    @classmethod
    def get_saved_lead(cls, db: Session, saved_lead_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single saved lead with joined details."""
        row = (
            db.query(SavedLead, Company, Contact)
            .join(Company, SavedLead.company_id == Company.id)
            .outerjoin(Contact, SavedLead.contact_id == Contact.id)
            .filter(SavedLead.id == saved_lead_id)
            .first()
        )
        if not row:
            return None

        saved, comp, cont = row
        return {
            "id": saved.id,
            "saved_at": saved.saved_at.strftime("%Y-%m-%d %H:%M:%S") if saved.saved_at else None,
            "search_keyword": saved.search_keyword,
            "source_name": saved.source_name,
            "source_url": saved.source_url,
            "evidence": saved.evidence,
            "company_name": comp.name,
            "website": comp.website,
            "industry": comp.industry,
            "country": comp.country,
            "city": comp.city,
            "decision_maker_name": cont.full_name if cont else None,
            "job_title": cont.job_title if cont else None,
            "business_email": cont.email if cont else None,
            "business_phone": cont.business_phone if cont else None,
        }

    @classmethod
    def delete_saved_lead(cls, db: Session, saved_lead_id: str) -> bool:
        """Deletes a saved lead from saved_leads."""
        rec = db.query(SavedLead).filter(SavedLead.id == saved_lead_id).first()
        if not rec:
            return False
        db.delete(rec)
        db.commit()
        return True

    @classmethod
    def get_saved_count(cls, db: Session) -> int:
        """Returns total count of saved leads for navbar badges."""
        return db.query(SavedLead).count()
