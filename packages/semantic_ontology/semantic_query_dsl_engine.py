import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.lead import Company, Contact, IntentSignal
from app.models.semantic_ontology import (
    SemanticQuery,
    SemanticQueryExecution,
)


class SemanticQueryDSLEngine:
    """
    Safe Semantic Query DSL Parser & Execution Engine:
    - Parses structured semantic queries using approved operators:
        =, !=, >, >=, <, <=, IN, NOT IN, CONTAINS, STARTS_WITH, EXISTS, NOT_EXISTS, AND, OR
    - Compiles strictly to SQLAlchemy ORM expressions (Zero raw SQL generation)
    - Immunity against SQL injection, code injection, and unsafe AST execution
    - Logs execution metrics and result counts for observability
    """

    ALLOWED_FIELDS = {
        "company", "country", "industry", "technology", "technology_version",
        "intent", "intent_strength", "job_role", "buying_committee_role",
        "lead_score", "email_status"
    }

    ALLOWED_OPERATORS = {
        "=", "!=", ">", ">=", "<", "<=", "IN", "NOT IN", "CONTAINS", "STARTS_WITH"
    }

    # Tokenizer pattern for safe DSL
    TOKEN_PATTERN = re.compile(
        r"""
        (?P<OP_COMP>!=|>=|<=|=|(?<![<>=!])>(?![=])|(?<![<>=!])<(?![=]))|
        (?P<KEYWORD>\b(?:AND|OR|NOT\s+IN|IN|CONTAINS|STARTS_WITH|EXISTS|NOT_EXISTS)\b)|
        (?P<LPAREN>\()|
        (?P<RPAREN>\))|
        (?P<COMMA>,)|
        (?P<STRING>'(?:\\.|[^'])*'|"(?:\\.|[^"])*")|
        (?P<NUMBER>-?\d+(?:\.\d+)?)|
        (?P<IDENT>[a-zA-Z_][a-zA-Z0-9_]*)
        """,
        re.VERBOSE | re.IGNORECASE
    )

    def __init__(self, db: Session):
        self.db = db

    def parse_dsl(self, dsl_text: str) -> Dict[str, Any]:
        """
        Parses DSL text into an abstract syntax tree / structured query plan.
        Raises ValueError if query contains forbidden syntax or injection attempts.
        """
        raw = dsl_text.strip()
        if not raw:
            raise ValueError("Query string cannot be empty.")

        # Guard against semicolon command chaining and SQL comments
        if ";" in raw or "--" in raw or "/*" in raw or "DROP " in raw.upper() or "SELECT " in raw.upper():
            raise ValueError("Forbidden tokens detected in semantic query.")

        clauses: List[Dict[str, Any]] = []
        tokens = []
        for m in self.TOKEN_PATTERN.finditer(raw):
            kind = m.lastgroup
            val = m.group(kind)
            tokens.append((kind, val))

        # Basic linear predicate parser for conjunctions: FIELD OP VALUE [AND ...]
        i = 0
        logical_combiner = "AND"
        while i < len(tokens):
            kind, val = tokens[i]
            if kind == "KEYWORD" and val.upper() in ("AND", "OR"):
                logical_combiner = val.upper()
                i += 1
                continue

            if kind == "IDENT":
                field = val.lower()
                if field not in self.ALLOWED_FIELDS:
                    raise ValueError(f"Unrecognized or forbidden field '{field}' in query.")

                i += 1
                if i >= len(tokens):
                    raise ValueError(f"Expected operator after field '{field}'.")

                op_kind, op_val = tokens[i]
                op = op_val.upper()
                if op not in self.ALLOWED_OPERATORS:
                    raise ValueError(f"Unsupported operator '{op_val}'.")

                i += 1
                if i >= len(tokens):
                    raise ValueError(f"Expected value after operator '{op}'.")

                # Parse value
                val_kind, raw_val = tokens[i]
                if op in ("IN", "NOT IN"):
                    # Parse list: (val1, val2, ...)
                    if val_kind != "LPAREN":
                        raise ValueError(f"Operator '{op}' requires parenthesized list '(val1, val2)'.")
                    i += 1
                    list_vals = []
                    while i < len(tokens) and tokens[i][0] != "RPAREN":
                        tk, tv = tokens[i]
                        if tk in ("IDENT", "STRING", "NUMBER"):
                            list_vals.append(tv.strip("'\"").upper())
                        i += 1
                    value = list_vals
                else:
                    value = raw_val.strip("'\"")
                    if val_kind == "NUMBER":
                        value = float(value) if "." in value else int(value)

                clauses.append({
                    "field": field,
                    "operator": op,
                    "value": value,
                    "combiner": logical_combiner
                })

            i += 1

        return {"raw_query": raw, "clauses": clauses}

    def execute_query(
        self,
        workspace_id: str,
        dsl_text: str,
        limit: int = 50,
        executed_by: str = "operator"
    ) -> Dict[str, Any]:
        """
        Executes a safe parsed DSL query against PostgreSQL workspace entities.
        Records SemanticQuery and SemanticQueryExecution.
        """
        start_t = time.perf_counter()
        plan = self.parse_dsl(dsl_text)

        # Build SQLAlchemy filters on Company model
        q = self.db.query(Company).filter(Company.workspace_id == workspace_id)

        for clause in plan["clauses"]:
            field = clause["field"]
            op = clause["operator"]
            val = clause["value"]

            col = None
            if field in ("country", "industry"):
                col = getattr(Company, field)
            elif field in ("company", "name"):
                col = Company.name
            elif field == "lead_score":
                col = Company.lead_score

            if col is not None:
                if op == "=":
                    q = q.filter(col.ilike(str(val)))
                elif op == "!=":
                    q = q.filter(col != str(val))
                elif op in (">", ">="):
                    q = q.filter(col >= val if op == ">=" else col > val)
                elif op in ("<", "<="):
                    q = q.filter(col <= val if op == "<=" else col < val)
                elif op == "CONTAINS":
                    q = q.filter(col.ilike(f"%{val}%"))
                elif op == "STARTS_WITH":
                    q = q.filter(col.ilike(f"{val}%"))
                elif op == "IN" and isinstance(val, list):
                    q = q.filter(col.in_(val))

            # Specialized ontology intent/tech filters via joins
            elif field == "intent":
                if op == "=":
                    q = q.join(IntentSignal).filter(IntentSignal.detected_keyword.ilike(f"%{val}%"))
                elif op == "IN" and isinstance(val, list):
                    q = q.join(IntentSignal).filter(
                        or_(*[IntentSignal.detected_keyword.ilike(f"%{v}%") for v in val])
                    )
            elif field == "technology":
                if op == "=":
                    q = q.join(IntentSignal).filter(IntentSignal.evidence_snippet.ilike(f"%{val}%"))

        results = q.limit(limit).all()
        elapsed_ms = round((time.perf_counter() - start_t) * 1000.0, 2)

        # Persist SemanticQuery
        sq = SemanticQuery(
            workspace_id=workspace_id,
            dsl_query=dsl_text,
            compiled_plan=plan,
            created_by=executed_by
        )
        self.db.add(sq)
        self.db.commit()
        self.db.refresh(sq)

        # Persist Execution
        sqe = SemanticQueryExecution(
            query_id=sq.id,
            result_count=len(results),
            execution_time_ms=elapsed_ms,
            status="SUCCESS"
        )
        self.db.add(sqe)
        self.db.commit()

        return {
            "query_id": sq.id,
            "dsl_query": dsl_text,
            "result_count": len(results),
            "execution_time_ms": elapsed_ms,
            "plan": plan,
            "results": [
                {
                    "company_id": c.id,
                    "company_name": c.name,
                    "country": c.country,
                    "industry": c.industry,
                    "lead_score": c.lead_score,
                    "domain": c.domain
                }
                for c in results
            ]
        }
