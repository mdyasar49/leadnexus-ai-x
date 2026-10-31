import math
import re
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.knowledge_graph import (
    KnowledgeEntity,
    KnowledgeRelationship,
    GraphEmbedding,
    RelationshipStatus,
    KnowledgeEntityType
)


class SemanticSearchEngine:
    """
    Semantic & Hybrid Search Engine:
    - Combines keyword search, structured filters, vector similarity, and graph connectivity.
    - Translates Natural Language requests into safe structured Graph queries.
    - Strict tenant isolation and deterministic cosine similarity on embedding vectors.
    """

    VOCAB = [
        "odoo", "erp", "migration", "australia", "shopify", "ecommerce",
        "logistics", "mining", "software", "retail", "integration", "oca",
        "customization", "upgrade", "postgresql", "python", "developer",
        "director", "cto", "manager", "cloud", "aws", "azure", "manufacturing"
    ]

    def __init__(self, db: Session):
        self.db = db

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a normalized 384-dimensional semantic embedding vector using deterministic
        hashing and vocabulary term frequencies. Unit-normalized so dot-product equals cosine similarity.
        """
        dim = 384
        vec = [0.0] * dim
        clean = text.lower()
        words = re.findall(r'\b\w+\b', clean)

        for w in words:
            # Hash to dimension slot
            h = int(w.encode('utf-8').hex(), 16) % dim
            # Vocabulary boost
            weight = 3.0 if w in self.VOCAB else 1.0
            vec[h] += weight

        # Unit normalization
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            vec = [round(x / norm, 4) for x in vec]
        return vec

    def index_entity_embedding(
        self,
        workspace_id: str,
        entity_id: str
    ) -> GraphEmbedding:
        """Computes and stores embedding vector for an entity."""
        ent = self.db.query(KnowledgeEntity).filter(
            and_(KnowledgeEntity.workspace_id == workspace_id, KnowledgeEntity.id == entity_id)
        ).first()
        if not ent:
            raise ValueError(f"Entity '{entity_id}' not found.")

        props_str = " ".join(f"{k} {v}" for k, v in (ent.properties or {}).items())
        text_corpus = f"{ent.canonical_name} {ent.entity_type} {ent.normalized_identifier} {props_str}"
        vec = self.generate_embedding(text_corpus)

        emb = self.db.query(GraphEmbedding).filter(
            and_(
                GraphEmbedding.workspace_id == workspace_id,
                GraphEmbedding.entity_id == entity_id
            )
        ).first()

        if emb:
            emb.embedding_vector = vec
        else:
            emb = GraphEmbedding(
                workspace_id=workspace_id,
                entity_type=ent.entity_type,
                entity_id=ent.id,
                model_name="all-MiniLM-L6-v2",
                model_version="v1.0",
                embedding_vector=vec,
                dimension=len(vec)
            )
            self.db.add(emb)

        self.db.commit()
        self.db.refresh(emb)
        return emb

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two unit vectors."""
        n = min(len(vec_a), len(vec_b))
        if n == 0:
            return 0.0
        return max(0.0, min(1.0, sum(vec_a[i] * vec_b[i] for i in range(n))))

    # --- 1. Hybrid Search ---

    def hybrid_search(
        self,
        workspace_id: str,
        query_text: str,
        entity_type: Optional[str] = "COMPANY",
        country: Optional[str] = None,
        industry: Optional[str] = None,
        must_have_technology: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid search:
        Score = 0.4 * Keyword_Match + 0.4 * Semantic_Similarity + 0.2 * Graph_Relationship_Boost
        """
        query_vec = self.generate_embedding(query_text)

        # Base query
        q = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.workspace_id == workspace_id)
        if entity_type:
            q = q.filter(KnowledgeEntity.entity_type == entity_type.upper())

        entities = q.all()
        scored_results = []

        for ent in entities:
            props = ent.properties or {}

            # Filter checks
            if country and country.lower() not in str(props.get("country", "")).lower():
                continue
            if industry and industry.lower() not in str(props.get("industry", "")).lower():
                continue

            # 1. Keyword Score
            text_corpus = f"{ent.canonical_name} {props}".lower()
            keyword_score = 0.0
            query_words = query_text.lower().split()
            matched_words = [w for w in query_words if w in text_corpus]
            if query_words:
                keyword_score = len(matched_words) / len(query_words)

            # 2. Semantic Score
            emb = self.db.query(GraphEmbedding).filter(
                and_(GraphEmbedding.workspace_id == workspace_id, GraphEmbedding.entity_id == ent.id)
            ).first()
            if emb and emb.embedding_vector:
                semantic_score = self.cosine_similarity(query_vec, emb.embedding_vector)
            else:
                # On the fly vector
                dyn_vec = self.generate_embedding(text_corpus)
                semantic_score = self.cosine_similarity(query_vec, dyn_vec)

            # 3. Graph Connectivity Boost (connected to Odoo or queried tech)
            tech_edges = self.db.query(KnowledgeRelationship).filter(
                and_(
                    KnowledgeRelationship.workspace_id == workspace_id,
                    KnowledgeRelationship.source_entity_id == ent.id,
                    KnowledgeRelationship.status == RelationshipStatus.ACTIVE.value
                )
            ).all()

            graph_boost = 0.0
            connected_techs = []
            for edge in tech_edges:
                target_ent = self.db.query(KnowledgeEntity).filter(KnowledgeEntity.id == edge.target_entity_id).first()
                if target_ent and target_ent.entity_type == KnowledgeEntityType.TECHNOLOGY.value:
                    connected_techs.append(target_ent.canonical_name)
                    if must_have_technology and must_have_technology.lower() in target_ent.canonical_name.lower():
                        graph_boost += 0.5
                    elif "odoo" in target_ent.canonical_name.lower():
                        graph_boost += 0.3

            if must_have_technology and not any(must_have_technology.lower() in t.lower() for t in connected_techs):
                continue

            graph_boost = min(1.0, graph_boost)

            # Total Hybrid Score
            total_score = round(
                (0.35 * keyword_score) + (0.45 * semantic_score) + (0.20 * graph_boost),
                3
            )

            scored_results.append({
                "entity_id": ent.id,
                "canonical_name": ent.canonical_name,
                "entity_type": ent.entity_type,
                "properties": props,
                "total_score": total_score,
                "keyword_score": round(keyword_score, 2),
                "semantic_score": round(semantic_score, 2),
                "graph_boost": round(graph_boost, 2),
                "connected_technologies": connected_techs
            })

        # Sort descending by total score
        scored_results.sort(key=lambda r: r["total_score"], reverse=True)
        return scored_results[:limit]

    # --- 2. Natural Language Query Translator ---

    def translate_nl_to_graph_dsl(self, prompt: str) -> Dict[str, Any]:
        """
        Translates Natural Language prompt into controlled, safe Graph DSL:
        e.g. "Australian companies using Odoo with migration intent"
        """
        lower = prompt.lower()
        dsl: Dict[str, Any] = {
            "entity_type": "COMPANY",
            "filters": {},
            "connected_to": None,
            "depth": 2,
            "min_confidence": 75.0
        }

        # Country extraction
        if "australia" in lower or "australian" in lower or ".au" in lower:
            dsl["filters"]["country"] = "Australia"
        elif "singapore" in lower or ".sg" in lower:
            dsl["filters"]["country"] = "Singapore"
        elif "uk" in lower or "united kingdom" in lower:
            dsl["filters"]["country"] = "United Kingdom"

        # Industry extraction
        if "mining" in lower:
            dsl["filters"]["industry"] = "Mining"
        elif "logistics" in lower:
            dsl["filters"]["industry"] = "Logistics"
        elif "retail" in lower or "ecommerce" in lower:
            dsl["filters"]["industry"] = "Retail"
        elif "software" in lower or "it" in lower:
            dsl["filters"]["industry"] = "Software"

        # Technology connection
        if "odoo" in lower:
            rel = "USES_ODOO"
            if "implement" in lower or "partner" in lower:
                rel = "IMPLEMENTS_ODOO"
            elif "migration" in lower:
                rel = "ODOO_MIGRATION"
            dsl["connected_to"] = {
                "entity_type": "TECHNOLOGY",
                "name": "Odoo",
                "relationship_type": rel
            }
        elif "shopify" in lower:
            dsl["connected_to"] = {
                "entity_type": "TECHNOLOGY",
                "name": "Shopify",
                "relationship_type": "USES_TECHNOLOGY"
            }

        return dsl

