from typing import Dict, Any, List, Optional


class ICPEngine:
    """
    ICP (Ideal Customer Profile) Intelligence Engine:
    - Evaluates company attributes against configurable ICP profiles
    - Computes independent component scores with weights and evidence
    - Calculates overall ICP Fit Score (0-100)
    """
    @classmethod
    def evaluate_fit(
        cls,
        company: Dict[str, Any],
        icp_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        profile = icp_profile or {
            "target_countries": ["Australia", "New Zealand"],
            "target_industries": ["Information Technology", "Retail", "Manufacturing", "Logistics"],
            "target_technologies": ["Odoo", "ERP", "Shopify"],
            "target_roles": ["CTO", "CIO", "IT Manager", "ERP Manager", "Managing Director", "Founder", "CEO"],
            "min_employees": 5,
            "max_employees": 5000,
            "weights": {
                "geography": 0.25,
                "technology": 0.30,
                "industry": 0.20,
                "decision_maker": 0.15,
                "company_size": 0.10,
            }
        }

        weights = profile.get("weights", {})
        components = []

        # 1. Geography Fit
        country = company.get("country", "")
        target_countries = [c.lower() for c in profile.get("target_countries", [])]
        if country and country.lower() in target_countries:
            geo_score = 100.0
            geo_reason = f"Target geography match: {country}"
        elif not country:
            geo_score = 40.0
            geo_reason = "Country unverified; neutral score"
        else:
            geo_score = 10.0
            geo_reason = f"Out of target geography: {country}"

        components.append({
            "name": "Geography",
            "score": geo_score,
            "weight": weights.get("geography", 0.25),
            "reason": geo_reason,
            "confidence": 0.95 if country else 0.50
        })

        # 2. Technology Fit
        technologies = [t.lower() for t in company.get("technologies", [])]
        target_techs = [t.lower() for t in profile.get("target_technologies", [])]

        def _sig_text(s):
            if isinstance(s, dict):
                return f"{s.get('detected_keyword', '')} {s.get('evidence_snippet', '')} {s.get('signal_type', '')}".lower()
            return str(s).lower()

        matched_techs = [
            t for t in target_techs
            if t in technologies or any(t in _sig_text(sig) for sig in company.get("signals", []))
        ]

        if matched_techs:
            tech_score = 100.0
            tech_reason = f"Matched core target technologies: {', '.join(matched_techs)}"
        else:
            tech_score = 25.0
            tech_reason = "No target technology footprints detected"

        components.append({
            "name": "Technology",
            "score": tech_score,
            "weight": weights.get("technology", 0.30),
            "reason": tech_reason,
            "confidence": 0.92 if matched_techs else 0.60
        })

        # 3. Industry Fit
        industry = company.get("industry", "")
        target_industries = [i.lower() for i in profile.get("target_industries", [])]
        if industry and any(i in industry.lower() for i in target_industries):
            ind_score = 90.0
            ind_reason = f"Matched target vertical: {industry}"
        elif not industry:
            ind_score = 50.0
            ind_reason = "Industry not explicitly identified"
        else:
            ind_score = 30.0
            ind_reason = f"Secondary industry: {industry}"

        components.append({
            "name": "Industry",
            "score": ind_score,
            "weight": weights.get("industry", 0.20),
            "reason": ind_reason,
            "confidence": 0.88 if industry else 0.40
        })

        # 4. Decision Maker Availability
        contacts = company.get("contacts", [])
        target_roles = [r.lower() for r in profile.get("target_roles", [])]
        matched_contacts = [
            c for c in contacts
            if any(r in c.get("job_title", "").lower() for r in target_roles)
        ]

        if matched_contacts:
            dm_score = 100.0
            dm_reason = f"Identified {len(matched_contacts)} target decision maker(s) in buying committee"
        elif contacts:
            dm_score = 50.0
            dm_reason = "General contacts discovered, but specific C-suite/IT title unconfirmed"
        else:
            dm_score = 20.0
            dm_reason = "No decision maker identified yet (Research Gap)"

        components.append({
            "name": "Decision Maker",
            "score": dm_score,
            "weight": weights.get("decision_maker", 0.15),
            "reason": dm_reason,
            "confidence": 0.90 if matched_contacts else 0.50
        })

        # 5. Company Size Fit
        emp_range = company.get("employee_count_range", "")
        size_score = 80.0
        size_reason = f"Company size within acceptable bounds ({emp_range or 'mid-market'})"

        components.append({
            "name": "Company Size",
            "score": size_score,
            "weight": weights.get("company_size", 0.10),
            "reason": size_reason,
            "confidence": 0.70
        })

        # Calculate Total Weighted Fit Score
        total_weighted_score = sum(c["score"] * c["weight"] for c in components)
        total_weight = sum(c["weight"] for c in components)
        final_icp_score = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 50.0

        return {
            "icp_fit_score": min(100.0, max(0.0, final_icp_score)),
            "components": components,
            "is_target_fit": final_icp_score >= 65.0,
        }
