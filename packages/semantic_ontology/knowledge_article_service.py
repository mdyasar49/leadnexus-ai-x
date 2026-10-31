import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.semantic_ontology import (
    KnowledgeArticle,
    KnowledgeArticleVersion,
    KnowledgeArticleConcept,
    ArticleType,
)


class KnowledgeArticleService:
    """
    Internal Knowledge Management Service:
    - Authoring, versioning, and cataloging of internal technical research playbooks,
      taxonomy guides, and ontology definitions
    - Associates articles with canonical Concept records
    - Explicitly excluded from CRM/Sales activities
    """

    def __init__(self, db: Session):
        self.db = db

    def create_article(
        self,
        workspace_id: str,
        title: str,
        content: str,
        article_type: str = ArticleType.ONTOLOGY_DEFINITION.value,
        author: str = "analyst",
        concept_ids: Optional[List[str]] = None,
        source_references: Optional[List[str]] = None
    ) -> KnowledgeArticle:
        article = KnowledgeArticle(
            workspace_id=workspace_id,
            title=title,
            article_type=article_type.upper(),
            content=content,
            author=author,
            current_version="v1.0",
            status="PUBLISHED",
            source_references=source_references or []
        )
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)

        # Initial Version
        v = KnowledgeArticleVersion(
            article_id=article.id,
            version="v1.0",
            title=title,
            content=content,
            change_summary="Initial article draft",
            created_by=author
        )
        self.db.add(v)

        # Associate Concepts
        if concept_ids:
            for cid in concept_ids:
                assoc = KnowledgeArticleConcept(article_id=article.id, concept_id=cid)
                self.db.add(assoc)

        self.db.commit()
        self.db.refresh(article)
        return article

    def update_article(
        self,
        workspace_id: str,
        article_id: str,
        title: str,
        content: str,
        change_summary: str,
        updated_by: str = "analyst"
    ) -> KnowledgeArticle:
        article = self.db.query(KnowledgeArticle).filter(
            and_(KnowledgeArticle.workspace_id == workspace_id, KnowledgeArticle.id == article_id)
        ).first()
        if not article:
            raise ValueError(f"Knowledge article '{article_id}' not found.")

        # Increment version
        parts = article.current_version.lstrip("v").split(".")
        major = int(parts[0]) if len(parts) > 0 else 1
        minor = int(parts[1]) + 1 if len(parts) > 1 else 1
        new_version = f"v{major}.{minor}"

        article.title = title
        article.content = content
        article.current_version = new_version
        article.updated_at = datetime.now(timezone.utc)

        v = KnowledgeArticleVersion(
            article_id=article.id,
            version=new_version,
            title=title,
            content=content,
            change_summary=change_summary,
            created_by=updated_by
        )
        self.db.add(v)
        self.db.commit()
        self.db.refresh(article)
        return article

    def list_articles(
        self,
        workspace_id: str,
        article_type: Optional[str] = None,
        query: Optional[str] = None
    ) -> List[KnowledgeArticle]:
        q = self.db.query(KnowledgeArticle).filter(KnowledgeArticle.workspace_id == workspace_id)
        if article_type:
            q = q.filter(KnowledgeArticle.article_type == article_type.upper())
        if query:
            q = q.filter(KnowledgeArticle.title.ilike(f"%{query}%"))
        return q.order_by(desc(KnowledgeArticle.updated_at)).all()

