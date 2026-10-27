# Prompt optimisation (both)

Task model `openai/gpt-4o-mini`, reflection model `openai/gpt-4o-mini`, pool `golden`, 9 train / 7 val / 4 test cases, 176.6s.

## Scores on the real agents (same cases for every prompt)

| prompt | val | test (held out) | all cases |
|---|---|---|---|
| seed | 0.614 | 0.550 | 0.680 |
| dspy | 0.814 | 0.750 | 0.795 |
| adk (winner) | 0.829 | 0.725 | 0.790 |

Winner **adk**: +0.175 on held-out test cases versus the seed.

## Cases where adk differs from the seed

| case | split | expected | seed did | winner did | seed -> winner |
|---|---|---|---|---|---|
| BENCH-06-MAHARASHTRA-HOURS-ACT | test | policy_agent | no hand-off | policy_agent | 0.30 -> 1.00 |
| BENCH-15-ZOHO-REGULARIZATION | val | zoho_agent | zoho_agent | zoho_agent | 0.80 -> 0.90 |
| BENCH-17-GRATUITY-ELIGIBILITY | train | policy_agent | no hand-off | policy_agent | 0.20 -> 0.90 |
| BENCH-20-PROBATION-CONFIRMATION | val | policy_agent | no hand-off | policy_agent | 0.30 -> 1.00 |
| BENCH-21-NOTICE-PERIOD-HANDOVER | val | policy_agent | no hand-off | policy_agent | 0.20 -> 0.80 |
| BENCH-23-NEMO-OFFTOPIC-DEFENSE | val | no hand-off | no hand-off | no hand-off | 0.70 -> 0.80 |
| BENCH-25-MEMORY-HIERARCHY-RECALL | train | no hand-off | no hand-off | zoho_agent | 0.80 -> 0.10 |

## Legs

- **dspy** (dspy.GEPA, agent execution mocked): 20 metric calls, 2 candidates, improved on its own validation set: True.
- **adk** (google.adk GEPARootAgentPromptOptimizer, agent execution real): 13 metric calls, 1 candidates, improved on its own validation set: False.

## Seed prompt

```
You are an HR helper. Answer every question yourself in one or two sentences. Do not pass questions to other agents; they are slow.
```

## Winning prompt (adk)

```
You are an HR assistant. Answer every employee question with concise, accurate information, keeping in mind the relevant specialist areas. If a question relates to a specific area of HR policy, leave, timesheet issues, health guidelines, or Zoho People HRMS, clearly indicate if you are passing the question to the appropriate specialist. Always refer to the employee by their preferred name and ensure your responses convey necessary actionable items.
```
