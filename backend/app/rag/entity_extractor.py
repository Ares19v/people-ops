"""
PeopleOps Enterprise — GraphRAG Entity & Relation Extraction Engine
===================================================================
Domain-specific entity extraction and multi-hop graph resolution for:
- Maharashtra Shops & Establishments Act 2017 (Sections 13, 14, 15, 18)
- Maternity Benefit Act 1961 (Section 5)
- DPDP Act 2023 (Section 4)
- Enterprise Leave, Timesheet, and Occupational Health Policies

Libraries Used:
- `pydantic` (Schema modeling & validation)
- `networkx` (Local graph indexing, multi-hop neighborhood extraction)
- `neo4j` (Cloud Neo4j AuraDB Cypher queries & transactions)
- `litellm` (LLM-driven unstructured text triplet extraction fallback)
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core import policy_facts as pf
import networkx as nx

from app.rag.graph_schema import (
    GraphNodeType,
    GraphRelationType,
    HRDomainCategory,
    NodeSchema,
    RelationshipSchema,
    ExtractedEntity,
    GraphTraversalResult,
)

logger = logging.getLogger(__name__)


# ── 1. Canonical Domain Ontology Seed Data ──────────────────────────────────────

DOMAIN_NODES: List[NodeSchema] = [
    # ── Statutory Acts
    NodeSchema(
        id="act_maha_2017",
        label=GraphNodeType.STATUTORY_ACT,
        name="Maharashtra Shops and Establishments Act 2017",
        domain=HRDomainCategory.TIME_AND_ATTENDANCE.value,
        statutory_citation="Maharashtra Act LXI of 2017",
        properties={"jurisdiction": "Maharashtra, India", "year": 2017, "mandatory": True}
    ),
    NodeSchema(
        id="act_maternity_1961",
        label=GraphNodeType.STATUTORY_ACT,
        name="Maternity Benefit Act 1961",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Act No. 53 of 1961",
        properties={"jurisdiction": "Federal India", "year": 1961, "mandatory": True}
    ),
    NodeSchema(
        id="act_dpdp_2023",
        label=GraphNodeType.STATUTORY_ACT,
        name="Digital Personal Data Protection Act 2023",
        domain=HRDomainCategory.DATA_PRIVACY_AND_COMPLIANCE.value,
        statutory_citation="DPDP Act 2023, No. 22 of 2023",
        properties={"jurisdiction": "Federal India", "year": 2023, "mandatory": True}
    ),

    # ── Statutory Sections
    NodeSchema(
        id="sec_13_working_hours",
        label=GraphNodeType.STATUTORY_SECTION,
        name="Section 13: Opening, Closing Hours & Daily Limits",
        domain=HRDomainCategory.TIME_AND_ATTENDANCE.value,
        statutory_citation="Section 13, Maharashtra Act 2017",
        properties={"max_daily_hours": 9, "max_weekly_hours": 48}
    ),
    NodeSchema(
        id="sec_14_overtime_wages",
        label=GraphNodeType.STATUTORY_SECTION,
        name="Section 14: Overtime Working & Double Wages",
        domain=HRDomainCategory.COMPENSATION_AND_OVERTIME.value,
        statutory_citation="Section 14, Maharashtra Act 2017",
        properties={"overtime_multiplier": 2.0, "max_daily_spread_hours": 11, "quarterly_cap_hours": 125}
    ),
    NodeSchema(
        id="sec_15_rest_interval",
        label=GraphNodeType.STATUTORY_SECTION,
        name="Section 15: Mandatory Interval for Rest",
        domain=HRDomainCategory.TIME_AND_ATTENDANCE.value,
        statutory_citation="Section 15, Maharashtra Act 2017",
        properties={"min_rest_minutes": 30, "continuous_work_limit_hours": 5}
    ),
    NodeSchema(
        id="sec_18_leave_entitlements",
        label=GraphNodeType.STATUTORY_SECTION,
        name="Section 18: Statutory Leave with Wages & Casual Leaves",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Section 18, Maharashtra Act 2017",
        properties={"statutory_el_accrual_rate": "1 day per 20 days worked", "statutory_cl_quota": 8, "max_el_carryover": 45}
    ),
    NodeSchema(
        id="sec_5_maternity_benefit",
        label=GraphNodeType.STATUTORY_SECTION,
        name="Section 5: Right to Payment of Maternity Benefit",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Section 5, Maternity Benefit Act 1961",
        properties={"paid_maternity_weeks": 26, "medical_bonus_inr": 3500}
    ),
    NodeSchema(
        id="sec_4_dpdp_personal_data",
        label=GraphNodeType.STATUTORY_SECTION,
        name="Section 4: Grounds for Processing Personal Data & Tokenization",
        domain=HRDomainCategory.DATA_PRIVACY_AND_COMPLIANCE.value,
        statutory_citation="Section 4, DPDP Act 2023",
        properties={"requires_consent": True, "requires_tokenization": True}
    ),

    # ── Enterprise Policies
    NodeSchema(
        id="pol_earned_leave",
        label=GraphNodeType.ENTERPRISE_POLICY,
        name="Enterprise Earned Leave (EL) Policy 2026",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Company HR Handbook § 4.1",
        properties={"annual_quota": pf.quota("EL"), "accrual": "1.5 days/month", "carryover_cap": pf.max_accumulation("EL"), "encashable": True}
    ),
    NodeSchema(
        id="pol_casual_leave",
        label=GraphNodeType.ENTERPRISE_POLICY,
        name="Enterprise Casual Leave (CL) Policy 2026",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Company HR Handbook § 4.2",
        properties={"annual_quota": pf.quota("CL"), "max_consecutive_days": 3, "encashable": False, "lapses_dec_31": True}
    ),
    NodeSchema(
        id="pol_sick_leave",
        label=GraphNodeType.ENTERPRISE_POLICY,
        name="Enterprise Sick Leave (SL) & Medical Protocol",
        domain=HRDomainCategory.OCCUPATIONAL_HEALTH.value,
        statutory_citation="Company HR Handbook § 4.3",
        properties={"annual_quota": pf.quota("SL"), "med_cert_threshold_days": 2, "encashable": False}
    ),
    NodeSchema(
        id="pol_overtime_rules",
        label=GraphNodeType.ENTERPRISE_POLICY,
        name="Enterprise Work Hours & Overtime Policy",
        domain=HRDomainCategory.COMPENSATION_AND_OVERTIME.value,
        statutory_citation="Company HR Handbook § 5.1",
        properties={"daily_standard_hours": 9, "daily_hard_cap_hours": 11, "overtime_rate": "2.0x base hourly rate"}
    ),
    NodeSchema(
        id="pol_maternity_leave",
        label=GraphNodeType.ENTERPRISE_POLICY,
        name="Enterprise Maternity & Parental Policy",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Company HR Handbook § 4.4",
        properties={"paid_weeks": 26, "pre_natal_reimbursement_inr": 50000}
    ),
    NodeSchema(
        id="pol_group_medical_health",
        label=GraphNodeType.ENTERPRISE_POLICY,
        name="Enterprise Group Medical & Ergonomics Plan",
        domain=HRDomainCategory.OCCUPATIONAL_HEALTH.value,
        statutory_citation="Company HR Handbook § 6.2",
        properties={"sum_insured_inr": 500000, "covers_dependents": True, "standing_desk_reimbursement": True}
    ),

    # ── Legal Invariants & Hard Rules
    NodeSchema(
        id="inv_daily_11h_hard_cap",
        label=GraphNodeType.LEGAL_INVARIANT,
        name="Mandatory Daily 11-Hour Hard Ceiling",
        domain=HRDomainCategory.TIME_AND_ATTENDANCE.value,
        statutory_citation="Section 14(2), Maharashtra Act 2017",
        properties={"max_hours": 11.0, "is_hard_block": True, "overtime_allowed": True}
    ),
    NodeSchema(
        id="inv_overtime_2x_multiplier",
        label=GraphNodeType.LEGAL_INVARIANT,
        name="Statutory 2.0x Double Wage Rate for Overtime",
        domain=HRDomainCategory.COMPENSATION_AND_OVERTIME.value,
        statutory_citation="Section 14(1), Maharashtra Act 2017",
        properties={"multiplier": 2.0}
    ),
    NodeSchema(
        id="inv_el_accumulation_45d_cap",
        label=GraphNodeType.LEGAL_INVARIANT,
        name="Earned Leave 45-Day Maximum Accumulation Cap",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Section 18(1)(a), Maharashtra Act 2017",
        properties={"max_accumulated_days": 45}
    ),
    NodeSchema(
        id="inv_sick_cert_over_2_days",
        label=GraphNodeType.LEGAL_INVARIANT,
        name="Mandatory MBBS/MD Medical Certificate for >2 Consecutive Sick Days",
        domain=HRDomainCategory.OCCUPATIONAL_HEALTH.value,
        statutory_citation="Section 18(1)(b) & Company Health Policy § 4.3",
        properties={"threshold_consecutive_days": 2, "mandatory_doc": "Medical Certificate"}
    ),

    # ── Document Requirements
    NodeSchema(
        id="doc_mbbs_medical_cert",
        label=GraphNodeType.DOCUMENT_REQUIREMENT,
        name="Certified Medical Practitioner Certificate (MBBS/MD)",
        domain=HRDomainCategory.OCCUPATIONAL_HEALTH.value,
        statutory_citation="Maharashtra Labour Rules & Form F",
        properties={"practitioner_types": ["MBBS", "MD"], "validity_days": 15}
    ),
    NodeSchema(
        id="doc_maternity_declaration",
        label=GraphNodeType.DOCUMENT_REQUIREMENT,
        name="Form B Maternity Medical Notice & Fitness Declaration",
        domain=HRDomainCategory.LEAVE_MANAGEMENT.value,
        statutory_citation="Maternity Benefit Rules Form B",
        properties={"mandatory_prior_notice_weeks": 7}
    )
]

DOMAIN_RELATIONSHIPS: List[RelationshipSchema] = [
    # Act -> Sections
    RelationshipSchema(
        source_id="act_maha_2017",
        target_id="sec_13_working_hours",
        type=GraphRelationType.CONTAINS_SECTION,
        rule_description="Maharashtra Act 2017 establishes standard 9h/day and 48h/week working limits.",
        statutory_basis="Maharashtra Act LXI of 2017"
    ),
    RelationshipSchema(
        source_id="act_maha_2017",
        target_id="sec_14_overtime_wages",
        type=GraphRelationType.CONTAINS_SECTION,
        rule_description="Maharashtra Act 2017 mandates 2x overtime rate and 11h daily spread limit.",
        statutory_basis="Maharashtra Act LXI of 2017"
    ),
    RelationshipSchema(
        source_id="act_maha_2017",
        target_id="sec_15_rest_interval",
        type=GraphRelationType.CONTAINS_SECTION,
        rule_description="Maharashtra Act 2017 mandates 30-minute rest interval after 5h continuous work.",
        statutory_basis="Maharashtra Act LXI of 2017"
    ),
    RelationshipSchema(
        source_id="act_maha_2017",
        target_id="sec_18_leave_entitlements",
        type=GraphRelationType.CONTAINS_SECTION,
        rule_description="Maharashtra Act 2017 guarantees Earned Leave (1 per 20 days) and 8 days Casual Leave.",
        statutory_basis="Maharashtra Act LXI of 2017"
    ),
    RelationshipSchema(
        source_id="act_maternity_1961",
        target_id="sec_5_maternity_benefit",
        type=GraphRelationType.CONTAINS_SECTION,
        rule_description="Maternity Benefit Act mandates 26 weeks paid leave for eligible female employees.",
        statutory_basis="Maternity Benefit Act 1961"
    ),
    RelationshipSchema(
        source_id="act_dpdp_2023",
        target_id="sec_4_dpdp_personal_data",
        type=GraphRelationType.CONTAINS_SECTION,
        rule_description="DPDP Act 2023 establishes purpose limitation, consent, and personal data masking.",
        statutory_basis="DPDP Act 2023"
    ),

    # Section -> Invariants
    RelationshipSchema(
        source_id="sec_14_overtime_wages",
        target_id="inv_daily_11h_hard_cap",
        type=GraphRelationType.MANDATES_INVARIANT,
        rule_description="Under Section 14(2), no employee is permitted to work beyond 11 hours in any single day.",
        statutory_basis="Section 14(2), Maharashtra Act 2017"
    ),
    RelationshipSchema(
        source_id="sec_14_overtime_wages",
        target_id="inv_overtime_2x_multiplier",
        type=GraphRelationType.MANDATES_INVARIANT,
        rule_description="Under Section 14(1), any work exceeding 9 hours/day or 48 hours/week is remunerated at 2.0x normal wage rate.",
        statutory_basis="Section 14(1), Maharashtra Act 2017"
    ),
    RelationshipSchema(
        source_id="sec_18_leave_entitlements",
        target_id="inv_el_accumulation_45d_cap",
        type=GraphRelationType.MANDATES_INVARIANT,
        rule_description="Under Section 18(1)(a), unavailed Earned Leave accumulation cannot exceed 45 days.",
        statutory_basis="Section 18(1)(a), Maharashtra Act 2017"
    ),
    RelationshipSchema(
        source_id="sec_18_leave_entitlements",
        target_id="inv_sick_cert_over_2_days",
        type=GraphRelationType.MANDATES_INVARIANT,
        rule_description="Statutory framework supports mandatory medical documentation for illness absences exceeding 2 consecutive days.",
        statutory_basis="Section 18, Maharashtra Act 2017"
    ),

    # Section -> Enterprise Policies (GOVERNS & HIGHER BENEFIT OVERRIDES)
    RelationshipSchema(
        source_id="sec_18_leave_entitlements",
        target_id="pol_earned_leave",
        type=GraphRelationType.GOVERNS_POLICY,
        rule_description="Section 18 sets minimum 12 days EL; Enterprise policy provides higher benefit of 18 days per year.",
        statutory_basis="Section 18, Maharashtra Act 2017"
    ),
    RelationshipSchema(
        source_id="pol_earned_leave",
        target_id="sec_18_leave_entitlements",
        type=GraphRelationType.OVERRIDES_WITH_HIGHER_BENEFIT,
        rule_description="Company grants 18 days Earned Leave annually (1.5 days/month), exceeding the statutory minimum of 12 days.",
        statutory_basis="Company Leave Policy § 4.1"
    ),
    RelationshipSchema(
        source_id="sec_18_leave_entitlements",
        target_id="pol_casual_leave",
        type=GraphRelationType.GOVERNS_POLICY,
        rule_description="Company Casual Leave aligns exactly with statutory 8 days quota and non-carryover rules.",
        statutory_basis="Section 18(1)(b), Maharashtra Act 2017"
    ),
    RelationshipSchema(
        source_id="sec_14_overtime_wages",
        target_id="pol_overtime_rules",
        type=GraphRelationType.GOVERNS_POLICY,
        rule_description="Enterprise overtime compensation strictly enforces 2.0x pay and 11-hour daily cap.",
        statutory_basis="Section 14, Maharashtra Act 2017"
    ),
    RelationshipSchema(
        source_id="sec_5_maternity_benefit",
        target_id="pol_maternity_leave",
        type=GraphRelationType.GOVERNS_POLICY,
        rule_description="Company provides 26 weeks paid maternity leave plus INR 50,000 pre-natal medical reimbursement.",
        statutory_basis="Section 5, Maternity Benefit Act 1961"
    ),

    # Policy -> Invariants & Document Requirements
    RelationshipSchema(
        source_id="pol_sick_leave",
        target_id="inv_sick_cert_over_2_days",
        type=GraphRelationType.ENFORCES_RULE,
        rule_description="Sick leave exceeding 2 consecutive days triggers mandatory medical certificate validation.",
        statutory_basis="Company Health Policy § 4.3"
    ),
    RelationshipSchema(
        source_id="inv_sick_cert_over_2_days",
        target_id="doc_mbbs_medical_cert",
        type=GraphRelationType.REQUIRES_DOCUMENT,
        rule_description="A verified medical fitness certificate issued by a registered medical practitioner (MBBS/MD) is required.",
        statutory_basis="Medical Council of India / HR Policy § 4.3"
    ),
    RelationshipSchema(
        source_id="pol_maternity_leave",
        target_id="doc_maternity_declaration",
        type=GraphRelationType.REQUIRES_DOCUMENT,
        rule_description="Form B maternity notice must be submitted at least 7 weeks prior to expected date of confinement.",
        statutory_basis="Maternity Benefit Rules Form B"
    )
]


# ── 2. Entity & Relation Extraction Engine ──────────────────────────────────────

class GraphEntityExtractor:
    """Use-case specific entity extractor and multi-hop graph resolver for PeopleOps GraphRAG."""

    def __init__(self):
        self.nx_graph = nx.DiGraph()
        self._nodes_by_id: Dict[str, NodeSchema] = {}
        self._build_in_memory_graph()

    def _build_in_memory_graph(self):
        """Constructs NetworkX directed multi-graph from domain ontology nodes and edges."""
        for node in DOMAIN_NODES:
            self._nodes_by_id[node.id] = node
            self.nx_graph.add_node(
                node.id,
                label=node.label.value,
                name=node.name,
                domain=node.domain,
                citation=node.statutory_citation,
                properties=node.properties,
            )

        for rel in DOMAIN_RELATIONSHIPS:
            self.nx_graph.add_edge(
                rel.source_id,
                rel.target_id,
                type=rel.type.value,
                rule=rel.rule_description,
                statutory_basis=rel.statutory_basis,
                properties=rel.properties,
            )

    def extract_entities_from_query(self, query: str) -> List[ExtractedEntity]:
        """Deterministic pattern matching and canonical entity resolution across HR domains."""
        q_norm = query.lower()
        extracted: List[ExtractedEntity] = []
        seen_ids: Set[str] = set()

        # Entity Keyword & Alias Mapping
        domain_patterns: List[Tuple[re.Pattern, str, GraphNodeType, float]] = [
            # Statutory Acts & Sections
            (re.compile(r"\b(maharashtra(\s+shops)?|section\s*14|overtime\s*wage|double\s*rate)\b"), "sec_14_overtime_wages", GraphNodeType.STATUTORY_SECTION, 0.98),
            (re.compile(r"\b(section\s*13|working\s*hours|daily\s*limit|weekly\s*hours|48\s*hours|9\s*hours)\b"), "sec_13_working_hours", GraphNodeType.STATUTORY_SECTION, 0.98),
            (re.compile(r"\b(section\s*15|rest\s*interval|lunch\s*break|continuous\s*work)\b"), "sec_15_rest_interval", GraphNodeType.STATUTORY_SECTION, 0.98),
            (re.compile(r"\b(section\s*18|leave\s*law|statutory\s*leave|annual\s*leave\s*act)\b"), "sec_18_leave_entitlements", GraphNodeType.STATUTORY_SECTION, 0.98),
            (re.compile(r"\b(maternity\s*(benefit|act|leave|section\s*5)|26\s*weeks)\b"), "sec_5_maternity_benefit", GraphNodeType.STATUTORY_SECTION, 0.98),
            (re.compile(r"\b(dpdp|privacy|personal\s*data|token\s*vault|masking)\b"), "sec_4_dpdp_personal_data", GraphNodeType.STATUTORY_SECTION, 0.95),

            # Policies & Leave Types
            (re.compile(r"\b(earned\s*leave|privilege\s*leave|\bel\b|annual\s*leave|vacation\s*quota)\b"), "pol_earned_leave", GraphNodeType.ENTERPRISE_POLICY, 0.95),
            (re.compile(r"\b(casual\s*leave|\bcl\b|urgent\s*leave)\b"), "pol_casual_leave", GraphNodeType.ENTERPRISE_POLICY, 0.95),
            (re.compile(r"\b(sick\s*leave|\bsl\b|medical\s*leave|illness|doctor|hospital|fever)\b"), "pol_sick_leave", GraphNodeType.ENTERPRISE_POLICY, 0.95),
            (re.compile(r"\b(overtime|extra\s*hours|11\s*hours|12\s*hours|10\s*hours|logged\s*hours)\b"), "pol_overtime_rules", GraphNodeType.ENTERPRISE_POLICY, 0.95),
            (re.compile(r"\b(health\s*insurance|medical\s*cover|standing\s*desk|ergonomic)\b"), "pol_group_medical_health", GraphNodeType.ENTERPRISE_POLICY, 0.92),

            # Invariants & Caps
            (re.compile(r"\b(11\s*hours?|daily\s*cap|hard\s*ceiling|max\s*hours\s*in\s*a\s*day)\b"), "inv_daily_11h_hard_cap", GraphNodeType.LEGAL_INVARIANT, 0.99),
            (re.compile(r"\b(2x|double\s*rate|double\s*pay|overtime\s*rate|multiplier)\b"), "inv_overtime_2x_multiplier", GraphNodeType.LEGAL_INVARIANT, 0.98),
            (re.compile(r"\b(45\s*days?|accumulation\s*cap|carry\s*forward\s*limit)\b"), "inv_el_accumulation_45d_cap", GraphNodeType.LEGAL_INVARIANT, 0.98),
            (re.compile(r"\b(medical\s*cert|doctor(\'s)?\s*(note|certificate)|mbbs|md\s*certificate|2\s*consecutive\s*days?|3\s*days\s*sick)\b"), "inv_sick_cert_over_2_days", GraphNodeType.LEGAL_INVARIANT, 0.99),
            (re.compile(r"\b(mbbs|registered\s*medical\s*practitioner|fitness\s*cert)\b"), "doc_mbbs_medical_cert", GraphNodeType.DOCUMENT_REQUIREMENT, 0.95),
        ]

        for pattern, node_id, ent_type, conf in domain_patterns:
            match = pattern.search(q_norm)
            if match and node_id not in seen_ids and node_id in self._nodes_by_id:
                node_obj = self._nodes_by_id[node_id]
                extracted.append(
                    ExtractedEntity(
                        raw_text=match.group(0),
                        entity_type=ent_type,
                        canonical_id=node_id,
                        confidence=conf,
                        matched_domain=node_obj.domain,
                        extracted_attributes=node_obj.properties
                    )
                )
                seen_ids.add(node_id)

        return extracted

    def resolve_subgraph(self, query: str, max_hops: int = 2) -> GraphTraversalResult:
        """Extracts entities, performs multi-hop neighborhood traversal, and synthesizes authoritative context."""
        matched_entities = self.extract_entities_from_query(query)
        if not matched_entities:
            # Fallback broad match across node names and properties
            q_tokens = set(query.lower().split())
            for nid, node in self._nodes_by_id.items():
                name_tokens = set(node.name.lower().split())
                if len(q_tokens.intersection(name_tokens)) >= 1:
                    matched_entities.append(
                        ExtractedEntity(
                            raw_text=node.name,
                            entity_type=node.label,
                            canonical_id=nid,
                            confidence=0.80,
                            matched_domain=node.domain,
                            extracted_attributes=node.properties
                        )
                    )

        # Collect k-hop subgraph nodes and relationships
        subgraph_node_ids: Set[str] = set()
        for ent in matched_entities:
            subgraph_node_ids.add(ent.canonical_id)
            if ent.canonical_id in self.nx_graph:
                # 1-hop successors
                for succ in self.nx_graph.successors(ent.canonical_id):
                    subgraph_node_ids.add(succ)
                    if max_hops >= 2:
                        for succ_2 in self.nx_graph.successors(succ):
                            subgraph_node_ids.add(succ_2)
                # 1-hop predecessors
                for pred in self.nx_graph.predecessors(ent.canonical_id):
                    subgraph_node_ids.add(pred)

        subgraph_nodes: List[NodeSchema] = [self._nodes_by_id[nid] for nid in subgraph_node_ids if nid in self._nodes_by_id]
        subgraph_relationships: List[RelationshipSchema] = []

        statutory_mandates = []
        policy_rules = []
        document_requirements = []
        citations_set = set()

        for u in subgraph_node_ids:
            for v in subgraph_node_ids:
                if self.nx_graph.has_edge(u, v):
                    edge_data = self.nx_graph.get_edge_data(u, v)
                    rel_type = edge_data.get("type", GraphRelationType.GOVERNS_POLICY.value)
                    rule = edge_data.get("rule", "")
                    basis = edge_data.get("statutory_basis")

                    rel_obj = RelationshipSchema(
                        source_id=u,
                        target_id=v,
                        type=GraphRelationType(rel_type) if rel_type in GraphRelationType._value2member_map_ else GraphRelationType.GOVERNS_POLICY,
                        rule_description=rule,
                        statutory_basis=basis,
                        properties=edge_data.get("properties", {})
                    )
                    subgraph_relationships.append(rel_obj)

                    u_name = self._nodes_by_id[u].name if u in self._nodes_by_id else u
                    v_name = self._nodes_by_id[v].name if v in self._nodes_by_id else v

                    if basis:
                        citations_set.add(basis)

                    if rel_type in [GraphRelationType.MANDATES_INVARIANT.value, GraphRelationType.CONTAINS_SECTION.value]:
                        statutory_mandates.append({"source": u_name, "target": v_name, "rule": rule, "citation": basis})
                    elif rel_type in [GraphRelationType.GOVERNS_POLICY.value, GraphRelationType.ENFORCES_RULE.value, GraphRelationType.OVERRIDES_WITH_HIGHER_BENEFIT.value]:
                        policy_rules.append({"policy": u_name, "target": v_name, "rule": rule, "citation": basis})
                    elif rel_type == GraphRelationType.REQUIRES_DOCUMENT.value:
                        document_requirements.append({"requirement": u_name, "document": v_name, "protocol": rule, "citation": basis})

        # Synthesize clear contextual briefing for the agent
        synthesis_lines = []
        if statutory_mandates:
            synthesis_lines.append("### Statutory Legal Mandates (Maharashtra Shops & Establishments Act 2017):")
            for m in statutory_mandates[:4]:
                synthesis_lines.append(f"• **{m['source']} ➔ {m['target']}**: {m['rule']} (Citation: {m['citation'] or 'Statutory Act'})")

        if policy_rules:
            synthesis_lines.append("\n### Enterprise Policy Rules & Benefit Overrides:")
            for p in policy_rules[:4]:
                synthesis_lines.append(f"• **{p['policy']}**: {p['rule']}")

        if document_requirements:
            synthesis_lines.append("\n### Mandatory Documentation & Compliance Gates:")
            for d in document_requirements:
                synthesis_lines.append(f"• **{d['requirement']} ➔ {d['document']}**: {d['protocol']}")

        synthesis_context = "\n".join(synthesis_lines) if synthesis_lines else "No specific statutory graph invariants triggered."

        return GraphTraversalResult(
            matched_entities=matched_entities,
            subgraph_nodes=subgraph_nodes,
            subgraph_relationships=subgraph_relationships,
            statutory_mandates=statutory_mandates,
            policy_rules=policy_rules,
            document_requirements=document_requirements,
            synthesis_context=synthesis_context,
            direct_citations=list(citations_set)
        )


graph_entity_extractor = GraphEntityExtractor()
