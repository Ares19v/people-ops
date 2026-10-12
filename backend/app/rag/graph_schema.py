"""
PeopleOps Enterprise — Domain Graph Schema & Knowledge Graph Taxonomy
======================================================================
Defines use-case specific ontology nodes, relationships, and invariants
for Indian Labour Laws (Maharashtra Shops & Establishments Act 2017,
Maternity Benefit Act 1961, DPDP Act 2023) and Enterprise HR Policies.

Libraries Used:
- pydantic (V2 for schema validation & typing)
- networkx (in-memory directed graph traversal)
- neo4j (cloud AuraDB graph storage & Cypher)
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class GraphNodeType(str, Enum):
    STATUTORY_ACT = "StatutoryAct"
    STATUTORY_SECTION = "StatutorySection"
    ENTERPRISE_POLICY = "EnterprisePolicy"
    LEGAL_INVARIANT = "LegalInvariant"
    HR_DOMAIN = "HRDomain"
    DOCUMENT_REQUIREMENT = "DocumentRequirement"
    PENALTY_OR_SANCTION = "PenaltyOrSanction"


class GraphRelationType(str, Enum):
    CONTAINS_SECTION = "CONTAINS_SECTION"
    GOVERNS_POLICY = "GOVERNS_POLICY"
    MANDATES_INVARIANT = "MANDATES_INVARIANT"
    ENFORCES_RULE = "ENFORCES_RULE"
    OVERRIDES_WITH_HIGHER_BENEFIT = "OVERRIDES_WITH_HIGHER_BENEFIT"
    REQUIRES_DOCUMENT = "REQUIRES_DOCUMENT"
    IMPOSES_SANCTION = "IMPOSES_SANCTION"
    BELONGS_TO_DOMAIN = "BELONGS_TO_DOMAIN"


class HRDomainCategory(str, Enum):
    LEAVE_MANAGEMENT = "Leave Management"
    TIME_AND_ATTENDANCE = "Time & Attendance"
    OCCUPATIONAL_HEALTH = "Occupational Health & Wellness"
    DATA_PRIVACY_AND_COMPLIANCE = "Data Privacy & Compliance"
    COMPENSATION_AND_OVERTIME = "Compensation & Overtime"
    TERMINATION_AND_NOTICE = "Termination & Notice Period"


class NodeSchema(BaseModel):
    id: str = Field(description="Unique node identifier, e.g. 'maha_act_2017_sec_14'")
    label: GraphNodeType = Field(description="Ontology node category")
    name: str = Field(description="Human-readable title or name")
    domain: Optional[str] = Field(default=None, description="Associated HR domain")
    statutory_citation: Optional[str] = Field(default=None, description="Legal section/citation")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Domain attributes (caps, rates, quotas)")


class RelationshipSchema(BaseModel):
    source_id: str = Field(description="Source node ID")
    target_id: str = Field(description="Target node ID")
    type: GraphRelationType = Field(description="Standardized relationship type")
    rule_description: str = Field(description="Plain-text legal or policy rule invariant")
    statutory_basis: Optional[str] = Field(default=None, description="Governing act/section")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge metadata")


class ExtractedEntity(BaseModel):
    raw_text: str = Field(description="Text segment matched in user query or policy text")
    entity_type: GraphNodeType = Field(description="Classified entity node type")
    canonical_id: str = Field(description="Matching ontology node ID")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    matched_domain: Optional[str] = None
    extracted_attributes: Dict[str, Any] = Field(default_factory=dict)


class GraphTraversalResult(BaseModel):
    matched_entities: List[ExtractedEntity]
    subgraph_nodes: List[NodeSchema]
    subgraph_relationships: List[RelationshipSchema]
    statutory_mandates: List[Dict[str, Any]]
    policy_rules: List[Dict[str, Any]]
    document_requirements: List[Dict[str, Any]]
    synthesis_context: str
    direct_citations: List[str]
