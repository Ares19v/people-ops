"""Enterprise Policy and Occupational Health Knowledge Graph using NetworkX."""

from dataclasses import dataclass
from typing import Any, Dict, List
import networkx as nx

@dataclass
class PolicyGraphResult:
    entities_matched: List[str]
    statutory_mandates: List[Dict[str, Any]]
    policy_restrictions: List[Dict[str, Any]]
    health_entitlements: List[Dict[str, Any]]
    synthesis: str

class EnterpriseKnowledgeGraph:
    """NetworkX directed knowledge graph mapping statutory laws to enterprise policies and health benefits."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self._seed_ontology()

    def _seed_ontology(self):
        # 1. Statutory Acts
        self.graph.add_node("Maharashtra_Act_2017", type="StatutoryAct", jurisdiction="Maharashtra")
        self.graph.add_node("Maternity_Benefit_Act_1961", type="StatutoryAct", jurisdiction="Federal_India")
        self.graph.add_node("DPDP_Act_2023", type="StatutoryAct", jurisdiction="Federal_India")

        # 2. Statutory Sections
        self.graph.add_node("Section_18_1_a", type="Section", act="Maharashtra_Act_2017", provision="1 day Earned Leave per 20 days worked; up to 18 days/yr; carry-forward capped at 45 days")
        self.graph.add_node("Section_18_1_b", type="Section", act="Maharashtra_Act_2017", provision="8 days Casual Leave annually; lapses Dec 31; non-encashable")
        self.graph.add_node("Section_13_1", type="Section", act="Maharashtra_Act_2017", provision="Maximum 9 hours/day and 48 hours/week standard work limit")
        self.graph.add_node("Section_14", type="Section", act="Maharashtra_Act_2017", provision="Overtime paid at 2.0x normal wage rate")
        self.graph.add_node("Maternity_Section_5", type="Section", act="Maternity_Benefit_Act_1961", provision="26 weeks paid maternity leave for eligible female employees")
        self.graph.add_node("DPDP_Section_4", type="Section", act="DPDP_Act_2023", provision="Strict purpose limitation, explicit consent collection, and personal data masking")

        # 3. Company Leave & Medical Policies
        self.graph.add_node("Earned_Leave", type="LeaveType", annual_quota=18, encashable=True)
        self.graph.add_node("Casual_Leave", type="LeaveType", annual_quota=8, encashable=False)
        self.graph.add_node("Sick_Leave", type="LeaveType", annual_quota=12, requires_medical_cert_days=2)
        self.graph.add_node("Maternity_Leave", type="LeaveType", paid_weeks=26)
        self.graph.add_node("Health_Insurance_Plan", type="HealthBenefit", coverage_inr=500000, covers_dependents=True)
        self.graph.add_node("Occupational_Health_Triage", type="HealthBenefit", covers_workplace_injuries=True)

        # 4. Connect Statutory Links
        self.graph.add_edge("Section_18_1_a", "Earned_Leave", relation="GOVERNS", rule="Baseline minimum 18 days accrual; 45 days accumulation cap")
        self.graph.add_edge("Section_18_1_b", "Casual_Leave", relation="GOVERNS", rule="8 days CL statutory quota; unencashable")
        self.graph.add_edge("Maternity_Section_5", "Maternity_Leave", relation="MANDATES", rule="26 weeks fully paid leave")
        self.graph.add_edge("DPDP_Section_4", "Health_Insurance_Plan", relation="PROTECTS", rule="Medical records & claim details are sensitive personal data")

        # 5. Connect Healthcare Requirements
        self.graph.add_edge("Sick_Leave", "Occupational_Health_Triage", relation="SUPPORTS", rule="Sick leave exceeding 2 consecutive days mandates verified clinical certificate")

    def search_graph(self, query: str) -> PolicyGraphResult:
        """Traverses the statutory and occupational health ontology to extract authoritative rules."""
        q_lower = query.lower()
        matched = []

        for node in self.graph.nodes:
            norm_node = node.lower().replace("_", " ")
            if norm_node in q_lower or any(word in q_lower.split() for word in norm_node.split() if len(word) > 3):
                matched.append(node)

        mandates = []
        restrictions = []
        health_benefits = []

        for node in matched:
            data = self.graph.nodes[node]
            # Check outgoing relations
            for target in self.graph.neighbors(node):
                edge = self.graph.get_edge_data(node, target)
                rel = edge.get("relation")
                rule = edge.get("rule")
                if rel in ["GOVERNS", "MANDATES"]:
                    mandates.append({"source": node, "target": target, "rule": rule})
                elif rel in ["PROTECTS", "RESTRICTS"]:
                    restrictions.append({"source": node, "target": target, "rule": rule})
                elif rel in ["SUPPORTS", "COVERS"]:
                    health_benefits.append({"source": node, "target": target, "rule": rule})

            # Check incoming relations (predecessors)
            for source in self.graph.predecessors(node):
                edge = self.graph.get_edge_data(source, node)
                rel = edge.get("relation")
                rule = edge.get("rule")
                if rel in ["GOVERNS", "MANDATES"]:
                    mandates.append({"source": source, "target": node, "rule": rule})
                elif rel in ["PROTECTS", "RESTRICTS"]:
                    restrictions.append({"source": source, "target": node, "rule": rule})
                elif rel in ["SUPPORTS", "COVERS"]:
                    health_benefits.append({"source": source, "target": node, "rule": rule})

        # Synthesize summary
        lines = []
        if mandates:
            lines.append("### Statutory Legal Mandates:")
            for m in mandates:
                lines.append(f"- **{m['source']} -> {m['target']}**: {m['rule']}")
        if health_benefits:
            lines.append("### Occupational Health & Medical Rules:")
            for h in health_benefits:
                lines.append(f"- **{h['source']}**: {h['rule']}")
        if restrictions:
            lines.append("### Compliance & Privacy Protections:")
            for r in restrictions:
                lines.append(f"- **{r['source']} -> {r['target']}**: {r['rule']}")

        synth_text = "\n".join(lines) if lines else "No direct statutory ontology links found."

        return PolicyGraphResult(
            entities_matched=matched,
            statutory_mandates=mandates,
            policy_restrictions=restrictions,
            health_entitlements=health_benefits,
            synthesis=synth_text
        )

enterprise_knowledge_graph = EnterpriseKnowledgeGraph()
