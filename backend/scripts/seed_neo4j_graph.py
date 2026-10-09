"""
PeopleOps — Neo4j Knowledge Graph Seeder & Sync Engine
======================================================
Builds the complete statutory labour law ontology, legal sections,
enterprise HR policies, and healthcare entitlements in Neo4j Aura.
"""
import os
import sys
import logging
from typing import Dict, Any, List
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
load_dotenv(os.path.join(backend_dir, ".env"))

from neo4j import GraphDatabase
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def seed_neo4j_graph(uri: str, user: str, password: str) -> Dict[str, Any]:
    """Connects to Neo4j and builds the statutory knowledge graph."""
    logger.info(f"Connecting to Neo4j at {uri} as {user}...")
    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=30.0)
    driver.verify_connectivity()
    logger.info("Successfully verified Neo4j Aura connectivity!")

    stats = {"nodes_created": 0, "relationships_created": 0}

    with driver.session() as session:
        # 1. Create Constraints / Indexes
        logger.info("1. Creating indexes and constraints...")
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (a:StatutoryAct) REQUIRE a.code IS UNIQUE;",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Section) REQUIRE s.section_id IS UNIQUE;",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:PolicyNode) REQUIRE p.name IS UNIQUE;",
            "CREATE INDEX IF NOT EXISTS FOR (p:PolicyNode) ON (p.title);",
            "CREATE INDEX IF NOT EXISTS FOR (s:Section) ON (s.title);"
        ]
        for c in constraints:
            try:
                session.run(c)
            except Exception as e:
                logger.warning(f"Constraint notice: {e}")

        # 2. Clear existing statutory ontology nodes
        logger.info("2. Clearing prior statutory graph nodes...")
        session.run("MATCH (n) WHERE n:StatutoryAct OR n:Section OR n:PolicyNode OR n:HealthBenefit DETACH DELETE n")

        # 3. Create Statutory Acts
        logger.info("3. Seeding Statutory Acts...")
        acts_cypher = """
        UNWIND $acts AS act
        CREATE (a:StatutoryAct {
            code: act.code,
            name: act.name,
            jurisdiction: act.jurisdiction,
            year: act.year,
            type: act.type,
            description: act.description
        })
        """
        acts_data = [
            {
                "code": "MH_SHOPS_2017",
                "name": "Maharashtra Shops and Establishments (Regulation of Employment and Conditions of Service) Act, 2017",
                "jurisdiction": "Maharashtra",
                "year": 2017,
                "type": "State Statutory Labour Act",
                "description": "Governs working hours, statutory overtime, earned leave caps, casual leaves, and working conditions in Maharashtra establishments."
            },
            {
                "code": "MATERNITY_1961",
                "name": "Maternity Benefit Act, 1961 (Amended 2017)",
                "jurisdiction": "Federal_India",
                "year": 1961,
                "type": "Central Statutory Social Welfare Act",
                "description": "Mandates 26 weeks of fully paid maternity leave, creche provisions, and protection against unlawful dismissal."
            },
            {
                "code": "DPDP_2023",
                "name": "Digital Personal Data Protection Act, 2023",
                "jurisdiction": "Federal_India",
                "year": 2023,
                "type": "Central Data Privacy & Governance Act",
                "description": "Regulates the processing of digital personal data, employee consent, PII/PHI protection, and purpose limitation."
            },
            {
                "code": "ESI_1948",
                "name": "Employees' State Insurance Act, 1948",
                "jurisdiction": "Federal_India",
                "year": 1948,
                "type": "Central Social Security & Medical Act",
                "description": "Governs medical leave certifications, sickness benefits, and workplace injury coverage."
            }
        ]
        session.run(acts_cypher, acts=acts_data)
        stats["nodes_created"] += len(acts_data)

        # 4. Create Statutory Sections
        logger.info("4. Seeding Statutory Sections...")
        sections_cypher = """
        UNWIND $sections AS sec
        CREATE (s:Section {
            section_id: sec.section_id,
            section_number: sec.section_number,
            title: sec.title,
            act_code: sec.act_code,
            provision: sec.provision,
            citation: sec.citation,
            daily_limit_hours: sec.daily_limit_hours,
            weekly_limit_hours: sec.weekly_limit_hours,
            overtime_rate: sec.overtime_rate,
            max_accumulation_days: sec.max_accumulation_days,
            annual_quota: sec.annual_quota
        })
        """
        sections_data = [
            {
                "section_id": "MH_SEC_13_1",
                "section_number": "Section 13(1)",
                "title": "Daily & Weekly Standard Working Hours",
                "act_code": "MH_SHOPS_2017",
                "provision": "No adult worker shall be required or allowed to work for more than nine hours in any day and forty-eight hours in any week.",
                "citation": "Maharashtra Shops and Establishments Act, 2017, Section 13(1)",
                "daily_limit_hours": 9.0,
                "weekly_limit_hours": 48.0,
                "overtime_rate": None,
                "max_accumulation_days": None,
                "annual_quota": None
            },
            {
                "section_id": "MH_SEC_14",
                "section_number": "Section 14",
                "title": "Overtime Wages & Double Remuneration",
                "act_code": "MH_SHOPS_2017",
                "provision": "Where a worker works beyond nine hours on any day or forty-eight hours in any week, overtime wages shall be paid at twice the ordinary rate of wages (2.0x). Total daily hours shall not exceed eleven hours.",
                "citation": "Maharashtra Shops and Establishments Act, 2017, Section 14",
                "daily_limit_hours": 11.0,
                "weekly_limit_hours": None,
                "overtime_rate": 2.0,
                "max_accumulation_days": None,
                "annual_quota": None
            },
            {
                "section_id": "MH_SEC_15",
                "section_number": "Section 15",
                "title": "Interval for Rest & Meal Breaks",
                "act_code": "MH_SHOPS_2017",
                "provision": "The periods of work of a worker shall be so fixed that no period shall exceed five hours without an interval for rest of at least thirty minutes.",
                "citation": "Maharashtra Shops and Establishments Act, 2017, Section 15",
                "daily_limit_hours": None,
                "weekly_limit_hours": None,
                "overtime_rate": None,
                "max_accumulation_days": None,
                "annual_quota": None
            },
            {
                "section_id": "MH_SEC_18_1_A",
                "section_number": "Section 18(1)(a)",
                "title": "Earned Leave Accrual & Accumulation Cap",
                "act_code": "MH_SHOPS_2017",
                "provision": "Every worker who has worked for not less than 240 days during a calendar year shall be allowed leave with wages at the rate of one day for every twenty days of work (minimum 18 days/yr). Accumulation of earned leave is capped at a statutory maximum of 45 days.",
                "citation": "Maharashtra Shops and Establishments Act, 2017, Section 18(1)(a)",
                "daily_limit_hours": None,
                "weekly_limit_hours": None,
                "overtime_rate": None,
                "max_accumulation_days": 45.0,
                "annual_quota": 18.0
            },
            {
                "section_id": "MH_SEC_18_1_B",
                "section_number": "Section 18(1)(b)",
                "title": "Casual Leave Statutory Entitlement",
                "act_code": "MH_SHOPS_2017",
                "provision": "Every worker shall be entitled to eight days of casual leave in every calendar year. Casual leave shall lapse at the end of the year and cannot be encashed.",
                "citation": "Maharashtra Shops and Establishments Act, 2017, Section 18(1)(b)",
                "daily_limit_hours": None,
                "weekly_limit_hours": None,
                "overtime_rate": None,
                "max_accumulation_days": 0.0,
                "annual_quota": 8.0
            },
            {
                "section_id": "MAT_SEC_5",
                "section_number": "Section 5",
                "title": "Paid Maternity Entitlement",
                "act_code": "MATERNITY_1961",
                "provision": "Eligible female employees are entitled to a maximum of 26 weeks of paid maternity leave, of which not more than 8 weeks shall precede the date of expected delivery.",
                "citation": "Maternity Benefit Act, 1961 (Amended 2017), Section 5",
                "daily_limit_hours": None,
                "weekly_limit_hours": None,
                "overtime_rate": None,
                "max_accumulation_days": None,
                "annual_quota": 26.0
            },
            {
                "section_id": "DPDP_SEC_4",
                "section_number": "Section 4",
                "title": "Personal Data Grounds & Purpose Limitation",
                "act_code": "DPDP_2023",
                "provision": "Personal data shall be processed only for lawful purposes with explicit consent or specific employment-related necessities, enforcing strict PII de-identification.",
                "citation": "Digital Personal Data Protection Act, 2023, Section 4",
                "daily_limit_hours": None,
                "weekly_limit_hours": None,
                "overtime_rate": None,
                "max_accumulation_days": None,
                "annual_quota": None
            },
            {
                "section_id": "ESI_SEC_57",
                "section_number": "Section 57",
                "title": "Medical Sickness Certification",
                "act_code": "ESI_1948",
                "provision": "Medical sickness leave exceeding two consecutive working days requires certification by a Registered Medical Practitioner (RMP).",
                "citation": "Employees' State Insurance Act, 1948, Section 57",
                "daily_limit_hours": None,
                "weekly_limit_hours": None,
                "overtime_rate": None,
                "max_accumulation_days": None,
                "annual_quota": 12.0
            }
        ]
        session.run(sections_cypher, sections=sections_data)
        stats["nodes_created"] += len(sections_data)

        # 5. Create Enterprise Policies & Benefits
        logger.info("5. Seeding Enterprise Policies and Healthcare Benefits...")
        policies_cypher = """
        UNWIND $policies AS pol
        CREATE (p:PolicyNode {
            name: pol.name,
            title: pol.title,
            category: pol.category,
            content: pol.content,
            annual_days: pol.annual_days,
            encashable: pol.encashable,
            requires_approval: pol.requires_approval,
            requires_medical_cert_days: pol.requires_medical_cert_days,
            coverage_amount_inr: pol.coverage_amount_inr
        })
        """
        policies_data = [
            {
                "name": "Intelera_Earned_Leave_Policy",
                "title": "Intelera Earned Leave (EL) Policy",
                "category": "Leave Management",
                "content": "Full-time employees accrue 1.5 to 2.0 days of Earned Leave per completed month (up to 24 days annually). Unused EL can be carried forward up to the statutory cap of 45 days. Encashment is permitted at separation.",
                "annual_days": 24.0,
                "encashable": True,
                "requires_approval": True,
                "requires_medical_cert_days": None,
                "coverage_amount_inr": None
            },
            {
                "name": "Intelera_Casual_Leave_Policy",
                "title": "Intelera Casual Leave (CL) Policy",
                "category": "Leave Management",
                "content": "All employees receive 8 days of Casual Leave on January 1st each year. CL is meant for unforeseen personal events and cannot be accumulated beyond December 31st or encashed.",
                "annual_days": 8.0,
                "encashable": False,
                "requires_approval": True,
                "requires_medical_cert_days": None,
                "coverage_amount_inr": None
            },
            {
                "name": "Intelera_Sick_Leave_Policy",
                "title": "Intelera Sick & Medical Leave (SL) Policy",
                "category": "Leave Management",
                "content": "Employees are provided 12 days of paid Sick Leave annually. Any sick leave spanning more than 2 consecutive working days requires a medical fitness certificate from a Registered Medical Practitioner.",
                "annual_days": 12.0,
                "encashable": False,
                "requires_approval": True,
                "requires_medical_cert_days": 2,
                "coverage_amount_inr": None
            },
            {
                "name": "Intelera_Overtime_Policy",
                "title": "Intelera Working Hours & Overtime Policy",
                "category": "Timesheet & Compensation",
                "content": "Standard workday is 9.0 hours including a 45-minute lunch break. Work performed in excess of 9 hours daily is logged as overtime and compensated at 2.0x hourly base rate. Daily total hours are capped at 11 hours maximum.",
                "annual_days": None,
                "encashable": True,
                "requires_approval": True,
                "requires_medical_cert_days": None,
                "coverage_amount_inr": None
            },
            {
                "name": "Intelera_Health_Benefits_Plan",
                "title": "Intelera Group Mediclaim & Occupational Health",
                "category": "Health & Benefits",
                "content": "Comprehensive corporate health insurance provides INR 5,00,000 family floater coverage for employee, spouse, and up to 2 children. Telehealth doctor consultation is available 24/7 via +91-800-INTELERA-CARE.",
                "annual_days": None,
                "encashable": False,
                "requires_approval": False,
                "requires_medical_cert_days": None,
                "coverage_amount_inr": 500000.0
            },
            {
                "name": "Intelera_DPDP_Privacy_Vault",
                "title": "Intelera DPDP Personal & Medical Privacy Framework",
                "category": "Compliance & Privacy",
                "content": "All Aadhaar numbers, PAN cards, and medical diagnosis terms are cryptographically masked via AES-256 reversible token vaulting before sending to LLM agents.",
                "annual_days": None,
                "encashable": False,
                "requires_approval": False,
                "requires_medical_cert_days": None,
                "coverage_amount_inr": None
            }
        ]
        session.run(policies_cypher, policies=policies_data)
        stats["nodes_created"] += len(policies_data)

        # 6. Create Graph Relationships (Edges)
        logger.info("6. Wiring graph relationships (CONTAINS, GOVERNS, MANDATES, PROTECTS, SUPPORTS)...")
        relationships_cypher = [
            """
            MATCH (a:StatutoryAct {code: 'MH_SHOPS_2017'}), (s:Section) WHERE s.act_code = 'MH_SHOPS_2017'
            MERGE (a)-[:CONTAINS]->(s)
            """,
            """
            MATCH (a:StatutoryAct {code: 'MATERNITY_1961'}), (s:Section) WHERE s.act_code = 'MATERNITY_1961'
            MERGE (a)-[:CONTAINS]->(s)
            """,
            """
            MATCH (a:StatutoryAct {code: 'DPDP_2023'}), (s:Section) WHERE s.act_code = 'DPDP_2023'
            MERGE (a)-[:CONTAINS]->(s)
            """,
            """
            MATCH (a:StatutoryAct {code: 'ESI_1948'}), (s:Section) WHERE s.act_code = 'ESI_1948'
            MERGE (a)-[:CONTAINS]->(s)
            """,
            """
            MATCH (s:Section {section_id: 'MH_SEC_18_1_A'}), (p:PolicyNode {name: 'Intelera_Earned_Leave_Policy'})
            MERGE (s)-[:GOVERNS {rule: 'Accrual baseline 18 days; maximum carry-forward accumulation cap 45 days'}]->(p)
            """,
            """
            MATCH (s:Section {section_id: 'MH_SEC_18_1_B'}), (p:PolicyNode {name: 'Intelera_Casual_Leave_Policy'})
            MERGE (s)-[:GOVERNS {rule: 'Mandatory 8 days statutory casual leave; lapses Dec 31; non-encashable'}]->(p)
            """,
            """
            MATCH (s:Section {section_id: 'MH_SEC_13_1'}), (p:PolicyNode {name: 'Intelera_Overtime_Policy'})
            MERGE (s)-[:MANDATES {rule: 'Standard daily hours capped at 9 hours, weekly standard capped at 48 hours'}]->(p)
            """,
            """
            MATCH (s:Section {section_id: 'MH_SEC_14'}), (p:PolicyNode {name: 'Intelera_Overtime_Policy'})
            MERGE (s)-[:MANDATES {rule: 'Overtime hours compensated at 2.0x ordinary wage rate; 11 hours daily maximum cap'}]->(p)
            """,
            """
            MATCH (s:Section {section_id: 'DPDP_SEC_4'}), (p:PolicyNode {name: 'Intelera_DPDP_Privacy_Vault'})
            MERGE (s)-[:MANDATES {rule: 'Reversible cryptographic token vaulting for PII/PHI protection under Indian DPDP Act'}]->(p)
            """,
            """
            MATCH (s:Section {section_id: 'ESI_SEC_57'}), (p:PolicyNode {name: 'Intelera_Sick_Leave_Policy'})
            MERGE (s)-[:GOVERNS {rule: 'Absences exceeding 2 consecutive days require medical practitioner certification'}]->(p)
            """,
            """
            MATCH (p1:PolicyNode {name: 'Intelera_Sick_Leave_Policy'}), (p2:PolicyNode {name: 'Intelera_Health_Benefits_Plan'})
            MERGE (p1)-[:SUPPORTS {protocol: 'Clinical triage and hospital reimbursement'}]->(p2)
            """,
            """
            MATCH (p1:PolicyNode {name: 'Intelera_Health_Benefits_Plan'}), (p2:PolicyNode {name: 'Intelera_DPDP_Privacy_Vault'})
            MERGE (p1)-[:PROTECTED_BY {standard: 'Zero-PII tokenization for clinical diagnoses'}]->(p2)
            """
        ]
        for query in relationships_cypher:
            session.run(query.strip())

        # Count total nodes and relationships
        res_nodes = session.run("MATCH (n) RETURN count(n) AS c")
        total_nodes = res_nodes.single()["c"]
        res_edges = session.run("MATCH ()-[r]->() RETURN count(r) AS c")
        total_edges = res_edges.single()["c"]

        stats["total_nodes"] = total_nodes
        stats["total_relationships"] = total_edges

    driver.close()
    logger.info(f"NEO4J SEEDING COMPLETED! Total Nodes: {total_nodes}, Total Relationships: {total_edges}")
    return stats

if __name__ == "__main__":
    uri = settings.NEO4J_URI
    user = settings.NEO4J_USER
    password = settings.NEO4J_PASSWORD
    print(f"Connecting to Neo4j: {uri} (user: {user})")
    res = seed_neo4j_graph(uri, user, password)
    print("Result:", res)
