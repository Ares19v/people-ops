import sys
from app.agents.intent_router import intent_router, QueryScope

test_queries = [
    # 1. Personal Ledger / Balances
    ('how many leave days do i have', ['leave_subagent'], QueryScope.PERSONAL_LEDGER),
    ('how much time off do i have left', ['leave_subagent'], QueryScope.PERSONAL_LEDGER),
    ('what is my remaining casual leave', ['leave_subagent'], QueryScope.PERSONAL_LEDGER),
    ('can i take next friday off', ['leave_subagent'], QueryScope.PERSONAL_LEDGER),
    ('show my leave balances', ['leave_subagent'], QueryScope.PERSONAL_LEDGER),
    ('i want to book 2 days vacation', ['leave_subagent'], QueryScope.PERSONAL_LEDGER),
    
    # 2. Normative Policy / Statutory Law
    ('what is the earned leave policy under maharashtra act', ['policy_rag_subagent'], QueryScope.NORMATIVE_POLICY),
    ('what are the statutory rules for notice period', ['policy_rag_subagent'], QueryScope.NORMATIVE_POLICY),
    ('explain section 18 of the shops and establishments act', ['policy_rag_subagent'], QueryScope.NORMATIVE_POLICY),
    ('what is the maximum overtime permitted by law', ['timesheet_subagent'], None), # Timesheet subagent handles overtime limits or policy
    ('what is the company policy for bereavement leave', ['policy_rag_subagent'], QueryScope.NORMATIVE_POLICY),
    
    # 3. Health & Occupational Triage
    ('i have a high fever, do i need a doctor certificate', ['health_subagent'], QueryScope.HEALTH_TRIAGE),
    ('what does our group health insurance mediclaim cover', ['health_subagent'], QueryScope.HEALTH_TRIAGE),
    ('i feel unwell today', ['health_subagent'], QueryScope.HEALTH_TRIAGE),
    
    # 4. Timesheet & Work Hours
    ('log 8 hours on project alpha for yesterday', ['timesheet_subagent'], QueryScope.TIMESHEET_LOGGING),
    ('show my timesheet summary for this week', ['timesheet_subagent'], QueryScope.TIMESHEET_LOGGING),
    ('i worked 10 hours yesterday how do i submit it', ['timesheet_subagent'], QueryScope.TIMESHEET_LOGGING),
    
    # 5. Zoho Sync
    ('sync my attendance with zoho people', ['zoho_subagent'], QueryScope.ZOHO_SYNC),
    ('check external zoho records', ['zoho_subagent'], QueryScope.ZOHO_SYNC),
    
    # 6. Compound Multi-Intent
    ('i have a high fever, how many sick days do i have left and do i need a doctor certificate', ['leave_subagent', 'health_subagent'], QueryScope.COMPOUND_HYBRID),
]

all_passed = True
for query, expected_tools, expected_scope in test_queries:
    route = intent_router.classify(query)
    is_ok = True
    for tool in expected_tools:
        if tool not in route.selected_tools:
            is_ok = False
            break
    if expected_scope and route.primary_scope != expected_scope:
        is_ok = False

    status = 'PASS' if is_ok else 'FAIL'
    if not is_ok:
        all_passed = False
    print(f'[{status}] "{query}"')
    print(f'       -> Tools: {route.selected_tools} (Expected: {expected_tools})')
    print(f'       -> Scope: {route.primary_scope.value}')

print(f'\nTEST SUITE SUMMARY: {"ALL SCENARIOS PASSED!" if all_passed else "SOME SCENARIOS FAILED"}')
if not all_passed:
    sys.exit(1)
