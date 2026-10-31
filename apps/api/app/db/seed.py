import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.rbac import Role, Permission, RolePermission
from app.models.source import ResearchSource, SourceType, SourceHealthStatus
from app.models.campaign import CampaignTemplate
from app.core.logging import get_logger

logger = get_logger("leadnexus.seed")

DEFAULT_PERMISSIONS = [
    ("organization.read", "View organization details"),
    ("organization.manage", "Manage organization settings"),
    ("workspace.read", "View workspace details"),
    ("workspace.manage", "Manage workspace"),
    ("users.read", "View team members"),
    ("users.invite", "Invite new users"),
    ("users.manage", "Manage team roles"),
    ("campaign.read", "View research campaigns"),
    ("campaign.create", "Create campaigns"),
    ("campaign.update", "Edit campaigns"),
    ("campaign.delete", "Delete campaigns"),
    ("campaign.run", "Trigger research runs"),
    ("company.read", "View discovered companies"),
    ("company.update", "Enrich company profiles"),
    ("contact.read", "View decision makers"),
    ("contact.update", "Update contacts"),
    ("verification.read", "View contact verification"),
    ("verification.run", "Execute verification"),
    ("review.read", "Access human review queue"),
    ("review.approve", "Approve or reject leads"),
    ("export.create", "Generate lead exports"),
    ("export.download", "Download exported files"),
    ("settings.read", "View platform settings"),
    ("settings.manage", "Modify platform settings"),
    ("audit.read", "View audit trail"),
]

DEFAULT_SOURCES = [
    {
        "code": "github",
        "key": "github",
        "name": "GitHub Intelligence",
        "description": "Scans public issues, PRs, discussions, and repository metadata for technical intent signals.",
        "source_type": SourceType.API,
        "is_active": True,
        "requires_auth": False,
        "health_status": SourceHealthStatus.HEALTHY,
        "rate_limit_per_minute": 60,
        "concurrency_limit": 5,
    },
    {
        "code": "company_website",
        "key": "company_website",
        "name": "Company Websites & Leadership",
        "description": "Compliant crawler checking public company pages (/about, /contact, /team) for verified leadership.",
        "source_type": SourceType.WEB,
        "is_active": True,
        "requires_auth": False,
        "health_status": SourceHealthStatus.HEALTHY,
        "rate_limit_per_minute": 120,
        "concurrency_limit": 10,
    },
    {
        "code": "public_directory",
        "key": "public_directory",
        "name": "Public Business Directories",
        "description": "Public business directories and government registries with permitted access.",
        "source_type": SourceType.DIRECTORY,
        "is_active": True,
        "requires_auth": False,
        "health_status": SourceHealthStatus.HEALTHY,
        "rate_limit_per_minute": 30,
        "concurrency_limit": 3,
    },
    {
        "code": "rss_forum",
        "key": "rss_forum",
        "name": "Public Discussion Feeds & Forums",
        "description": "Public community feeds, developer forums, and RSS notifications indicating enterprise tech migration.",
        "source_type": SourceType.RSS,
        "is_active": True,
        "requires_auth": False,
        "health_status": SourceHealthStatus.HEALTHY,
        "rate_limit_per_minute": 60,
        "concurrency_limit": 5,
    },
    {
        "code": "job_posting",
        "key": "job_posting",
        "name": "Hiring & Job Intelligence",
        "description": "Permitted job listings revealing expansion, modernization, and technology budget allocation.",
        "source_type": SourceType.JOB_BOARD,
        "is_active": True,
        "requires_auth": False,
        "health_status": SourceHealthStatus.HEALTHY,
        "rate_limit_per_minute": 60,
        "concurrency_limit": 5,
    },
]

DEFAULT_TEMPLATES = [
    {
        "code": "odoo_australia",
        "name": "Odoo ERP Australia High Intent",
        "category": "ERP",
        "description": "Discovers Australian companies actively seeking Odoo ERP implementation, migration from v14-v16, and integration partners.",
        "campaign_type": "ODOO",
        "config_defaults": {
            "country": "Australia",
            "state": "",
            "city": "Sydney, Melbourne, Brisbane, Perth",
            "industry": "Information Technology & Enterprise Software",
            "company_keywords": ["Odoo", "ERP", "Enterprise Resource Planning", "Supply Chain", "Manufacturing"],
            "intent_keywords": [
                "looking for Odoo partner",
                "Odoo migration",
                "Odoo implementation",
                "need Odoo integration",
                "upgrade from v14",
                "upgrade from v15",
                "upgrade from v16",
                "custom module",
                "POS integration"
            ],
            "target_job_titles": ["CEO", "Founder", "Managing Director", "CTO", "CIO", "IT Manager", "ERP Manager", "Operations Manager"],
            "sources": ["github", "company_website", "rss_forum", "job_posting"],
            "maximum_results": 100,
            "icp_rules": {
                "target_country": "Australia",
                "minimum_lead_score": 60
            }
        }
    },
    {
        "code": "zoho_india",
        "name": "Zoho CRM & ERP India",
        "category": "CRM",
        "description": "Targets mid-market Indian enterprises evaluating Zoho One, Zoho CRM implementation, and ERP replacements.",
        "campaign_type": "ZOHO",
        "config_defaults": {
            "country": "India",
            "state": "Maharashtra, Karnataka, Tamil Nadu, Delhi NCR",
            "city": "Bengaluru, Mumbai, Chennai, Hyderabad, Pune, Gurugram",
            "industry": "IT Services, SaaS, Manufacturing, FinTech",
            "company_keywords": ["Zoho", "Zoho One", "Zoho CRM", "Zoho Books", "Zoho Creator"],
            "intent_keywords": [
                "looking for Zoho partner",
                "Zoho implementation",
                "Zoho CRM migration",
                "Zoho Books integration",
                "Zoho Creator developer",
                "CRM migration"
            ],
            "target_job_titles": ["Founder", "CEO", "Managing Director", "VP of Sales", "CTO", "Operations Head"],
            "sources": ["github", "company_website", "rss_forum", "job_posting"],
            "maximum_results": 100,
            "icp_rules": {
                "target_country": "India",
                "minimum_lead_score": 60
            }
        }
    },
    {
        "code": "ecommerce_growth",
        "name": "E-Commerce & Retail Tech Leads",
        "category": "ECOMMERCE",
        "description": "Identifies e-commerce brands scaling infrastructure, migrating between Shopify Plus, Magento, and WooCommerce.",
        "campaign_type": "ECOMMERCE",
        "config_defaults": {
            "country": "Global",
            "industry": "Retail & Consumer Goods",
            "company_keywords": ["Shopify", "Magento", "WooCommerce", "BigCommerce", "Headless Commerce"],
            "intent_keywords": [
                "Shopify migration",
                "Magento 2 upgrade",
                "ERP connector",
                "custom payment gateway",
                "high volume checkout",
                "Shopify Plus partner"
            ],
            "target_job_titles": ["CEO", "E-Commerce Director", "Head of Digital", "CTO", "Operations Director"],
            "sources": ["github", "company_website", "job_posting"],
            "maximum_results": 100,
            "icp_rules": {
                "minimum_lead_score": 55
            }
        }
    },
]

async def seed_initial_data(db: AsyncSession):
    """Idempotently seeds permissions, roles, research sources, and campaign templates."""
    logger.info("[Database Seeder] Checking and seeding system records...")

    # 1. Seed Permissions
    for code, desc in DEFAULT_PERMISSIONS:
        stmt = select(Permission).where(Permission.code == code)
        if not (await db.execute(stmt)).scalar_one_or_none():
            db.add(Permission(code=code, name=code, description=desc))

    # 2. Seed Roles
    roles = ["ADMIN", "MANAGER", "RESEARCHER", "VIEWER"]
    for role_name in roles:
        stmt = select(Role).where(Role.code == role_name)
        if not (await db.execute(stmt)).scalar_one_or_none():
            db.add(Role(code=role_name, name=role_name, description=f"Standard {role_name.capitalize()} role"))
    await db.flush()

    # 3. Seed Research Sources
    for src_data in DEFAULT_SOURCES:
        stmt = select(ResearchSource).where(ResearchSource.code == src_data["code"])
        if not (await db.execute(stmt)).scalar_one_or_none():
            db.add(ResearchSource(**src_data))
    await db.flush()

    # 4. Seed Campaign Templates
    for tpl_data in DEFAULT_TEMPLATES:
        stmt = select(CampaignTemplate).where(CampaignTemplate.code == tpl_data["code"])
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            db.add(CampaignTemplate(
                code=tpl_data["code"],
                name=tpl_data["name"],
                category=tpl_data["category"],
                description=tpl_data["description"],
                campaign_type=tpl_data["campaign_type"],
                default_config=tpl_data["config_defaults"],
                is_active=True,
            ))
    await db.commit()
    logger.info("[Database Seeder] System seeding complete.")
