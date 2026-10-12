"""
PeopleOps Enterprise — Domain Knowledge Graph & Statutory Ontology
===================================================================
Manages statutory labour laws, enterprise leave rules, overtime invariants,
and occupational health protocols using NetworkX and GraphRAG Entity Extraction.
"""

from dataclasses import dataclass
from typing import Any, Dict, List
import networkx as nx

from app.rag.graph_schema import (
    GraphNodeType,
    GraphRelationType,
    HRDomainCategory,
    GraphTraversalResult,
)
from app.rag.entity_extractor import graph_entity_extractor


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
        self.extractor = graph_entity_extractor
        self.graph = self.extractor.nx_graph

    def search_graph(self, query: str) -> PolicyGraphResult:
        """Traverses the statutory and occupational health ontology using domain-specific entity extraction."""
        traversal: GraphTraversalResult = self.extractor.resolve_subgraph(query, max_hops=2)

        matched_names = [e.raw_text for e in traversal.matched_entities]

        return PolicyGraphResult(
            entities_matched=matched_names,
            statutory_mandates=traversal.statutory_mandates,
            policy_restrictions=traversal.policy_rules,
            health_entitlements=traversal.document_requirements,
            synthesis=traversal.synthesis_context
        )


enterprise_knowledge_graph = EnterpriseKnowledgeGraph()
