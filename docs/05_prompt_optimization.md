# Prompt grid-testing and optimisation: Google ADK and DSPy

Two additions, both runnable from a script (neither needs the backend or ngrok):

1. **ADK prompt x model grid.** The Langfuse grid has always tested prompt versions across models; ADK cannot do that
   natively, so `scripts/run_adk_grid.py` triggers it: every (prompt version, model) cell is run through ADK's own
   evaluators on the real agents.
2. **Prompt optimisation, two ways, on one engine.** DSPy and Google ADK each wrap the same GEPA library
   (`dspy 3.4.1` requires `gepa==0.1.4`, the version `google-adk 2.13.0` uses). They differ in what a metric call is:

| | DSPy leg | Google ADK leg |
|---|---|---|
| Wrapper | `dspy.GEPA` | `GEPARootAgentPromptOptimizer` |
| Agent execution | **mocked**: one predictor decides the hand-off; nothing after it runs | **real**: root + specialists + tools on the isolated SQLite database |
| A metric call costs | one LLM call | a full agent run (about 3 LLM calls) |
| Good for | exploring many rewrites cheaply | checking rewrites against what the agents really do |

## How the two are integrated

```
seed (poor) prompt
   |
   |--> DSPy GEPA  (mocked agent, many cheap calls) --> best DSPy prompt
   |                                                         | becomes the ADK seed (if it improved)
   |                                                         v
   '-----------------------------------------------> ADK GEPA (real agents, fewer costly calls) --> best ADK prompt
                                                             |
   seed, DSPy best and ADK best are all re-scored on the real agents, on held-out cases --> winner + report
```

Both legs use the same cases, the same train / validation / test split and the same score
(`app/optimization/common.py`), so their numbers mean the same thing:

    score = 0.7 * route + 0.3 * reply

* **route**: the first `transfer_to_agent` target equals the expected specialist; for guardrail cases (jailbreak,
  off-topic, PII, memory recall) *no* hand-off is expected.
* **reply**: the golden case's `must_contain_keywords` / `forbidden_terms` on the answer. The mock leg cannot see a
  specialist's answer, so it counts it as correct whenever a hand-off was expected.

Why this score: the root prompt decides routing and direct replies; it does not control the specialists' tool
arguments. Cases that write data (apply leave, log hours, Zoho sync) are excluded, because they change the database
between candidates. The 20 remaining golden cases are split stratified by route into train (reflection), validation
(candidate selection) and test (final comparison only).

## Run

Prerequisites: `backend/.venv` holds ADK 2.13.0 and DSPy (see `backend/requirements.txt`); `.env` has the
provider keys. Usable models in this project: `openai/gpt-4o-mini` and `groq/openai/gpt-oss-120b` (the Gemini key
returns 404).

```powershell
cd "C:\Users\Devansh Tyagi\Desktop\Intelera\people-ops"

# 1. ADK grid: prompt versions x models
npm run adk:grid -- --versions v12,v13 --models openai/gpt-4o-mini,groq/openai/gpt-oss-120b --metrics standard
npm run adk:grid -- --config grid.json --metrics fast          # same config shape as the Langfuse grid
npm run adk:grid -- --versions v12 --prompt-text poor="You are an HR bot." --models openai/gpt-4o-mini

# 2. Optimise a poor prompt: DSPy then ADK
npm run optimize:prompt                                         # defaults: misleading seed, 60 DSPy + 40 ADK calls
npm run optimize:prompt -- --dspy-calls 120 --adk-calls 90
npm run optimize:prompt -- --mode dspy --seed vague
npm run optimize:prompt -- --mode adk --seed @my_prompt.txt --reflection-model groq/openai/gpt-oss-120b
```

Reports are written to `backend/reports/` (`adk_grid_*.json`, `optimization_*.json` and `.md`). Nothing is published to
Langfuse unless `--publish-label gepa-candidate` is given (the `live`, `production` and `latest` labels are refused).
Before `npm run` works, `frontend` must have its dependencies installed as usual.

`--metrics` for the grid: `fast` (trajectory + ROUGE, no judge calls), `standard` (adds `final_response_match_v2`),
`full` (all ADK evaluators). The grid's composite is half tool trajectory, half the judged response metrics; "pass rate"
is the share of cases with composite >= 0.8 (ADK's own all-metrics status is reported as `adk_strict_pass_rate_percent`).
Cells run one after another because the model and the root prompt are process-wide settings of the agent fleet.

## Results of the first real runs (2026-10-26, task and reflection model `gpt-4o-mini`)

**ADK grid**, 4 items, `standard` metrics, judge `gpt-4o-mini` (`reports/adk_grid_20261026_195718.json`):

| prompt | gpt-oss-120b (Groq) | gpt-4o-mini |
|---|---|---|
| v12 | 1.000 | 0.750 |
| v13 | 1.000 | 0.750 |

**Optimisation**, seed *"You are an HR helper. Answer every question yourself in one or two sentences. Do not pass questions
to other agents; they are slow."*, 120 DSPy + 90 ADK metric calls, 371 s (`reports/optimization_20261026_195446.md`).
Scores below are all from the **real agents**:

| prompt | validation | test (4 cases, held out) | all 20 cases |
|---|---|---|---|
| seed | 0.600 | 0.750 | 0.670 |
| DSPy best | 0.714 | 0.750 | 0.710 |
| ADK best (seeded from DSPy) | 0.886 | 0.750 | 0.770 |

What this does and does not show:

* The ADK leg fixed what the seed got wrong: policy questions that were answered directly are now handed to the policy
  agent (BENCH-16, 20 and 21 went from 0.1-0.3 to 0.8-1.0 on validation).
* **The mock over-states gains.** The DSPy leg scored its own winner 0.97 on the mocked validation set, but only 0.714 on
  the same cases with real agents (seed 0.600). That gap is why the ADK leg exists and why the final comparison always uses
  real agents.
* **The held-out set is too small to conclude anything.** 4 test cases did not move (0.750 for all three); one of them,
  BENCH-24 (PII), needs the guardrail layer, which a root prompt cannot replace. The ADK winner also regressed on one training
  case (BENCH-07, overtime: now answered directly). Treat the result as a working pipeline with encouraging signs, not a
  proven improvement; widen the pool or repeat with other split seeds before trusting a gain.
* Results vary between runs (LLM sampling, 20 cases). Compare seeds and budgets over several runs.

## Cost and limits

* The 371 s run used about 120 cheap DSPy calls, about 100 agent runs and a few dozen reflection calls: cents on `gpt-4o-mini`.
* Groq's free tier is rate-limited (about 8k tokens/min); a multi-call agent turn on Groq waits and retries, so Groq runs are slower.
* Only the **root** prompt is optimised; sub-agent prompts stay as they are.
* A rewrite is only as safe as its tests: review the winning prompt (it is in the report) before promoting it anywhere.
  Candidate text is made ADK-safe (`{...}` becomes `[...]`, `{{organization_name}}` is rendered) by `to_adk_instruction`.

## Files

| File | Role |
|---|---|
| `app/optimization/runtime.py` | isolated ADK runtime (SQLite), `to_adk_instruction` |
| `app/optimization/metric.py` | composite score and metric presets for the grid |
| `app/optimization/adk_grid.py`, `scripts/run_adk_grid.py` | ADK prompt x model grid |
| `app/optimization/common.py` | cases, split, seed prompts, the shared score |
| `app/optimization/dspy_leg.py` | DSPy GEPA over the mocked root agent |
| `app/optimization/adk_leg.py` | ADK GEPA with `RouteSampler` running the real agents |
| `app/optimization/pipeline.py`, `scripts/run_prompt_optimization.py` | chains the legs, compares, writes the report |
| `tests/test_prompt_optimization.py` | offline tests (no LLM calls) |

## Dependency note

The repo has one Python environment, `backend/.venv` (Python 3.12), holding ADK 2.13.0, DSPy and everything else. The
`dev:backend`, `adk:web`, `adk:grid` and `optimize:prompt` scripts and run from `backend/` with `PYTHONPATH=.`.

## Publishing the GEPA winner to Langfuse

When GEPA beats the seed prompt, `scripts/run_prompt_optimization.py` pushes the winner to Langfuse automatically as a new
version of `peopleops-root-orchestrator` with the label `gepa-optimized` and the tag **GEPA Optimized**. It is never labelled
`live`; review it, then promote it yourself. `--no-publish` skips the push, `--publish-label` changes the label,
`--prompt-name` the prompt. Langfuse tags belong to the prompt name (all its versions show them); the per-version marker is
the `gepa-optimized` label plus the commit message, which records the seed and winner scores. Existing tags are kept.

## Comparing any two prompts on any agents

`scripts/run_adk_prompt_compare.py` (`npm run adk:compare -- <args>` from `frontend/`) runs prompt A on agent A against prompt B
on agent B on the same golden cases, with ADK's own evaluators, and prints and saves a grid (per-contestant scores, per-metric
averages, case-by-case results, winner, head-to-head record). Nothing has to be optimised: any Langfuse version or label, or
literal text, works. A contestant is `agent=` (root, leave, timesheet, health, policy, zoho), `prompt=` (Langfuse prompt name,
default the agent's own), one of `version=` / `label=` / `text=` (text=@file.txt reads a file), and optionally `model=`.

```
python scripts/run_adk_prompt_compare.py -c agent=root,version=12 -c agent=root,label=gepa-optimized
python scripts/run_adk_prompt_compare.py -c agent=leave,version=1 -c agent=leave,version=2
python scripts/run_adk_prompt_compare.py -c agent=policy,version=2,model=openai/gpt-4o-mini -c agent=health,label=live
```

Every contestant runs the same cases on the isolated SQLite database. If all contestants target one specialist, only the cases
that should reach that specialist are used (`--items` overrides). Differences under 0.05 are flagged as noise: with a handful
of cases they are not distinguishable. Reports go to `backend/reports/prompt_compare_<time>.{json,md}`.
