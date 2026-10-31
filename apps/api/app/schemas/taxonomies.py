"""Taxonomies and pre-defined choices schemas."""
from typing import List, Dict
from pydantic import BaseModel


class TaxonomyItem(BaseModel):
    id: str
    name: str
    description: str = ""
    suggested_sources: List[str] = []
    suggested_keywords: List[str] = []


class TaxonomiesResponse(BaseModel):
    industries: List[str]
    target_job_titles: List[str]
    intent_signals: List[Dict[str, str]]
    countries: List[str]
    standard_sources: List[Dict[str, str]]

