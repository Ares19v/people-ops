"""Head-to-head prompt comparison on Google ADK's evaluators: any prompt version on any agent vs another.

ADK's UI evaluates one agent at a time and has no "prompt v1 on agent A vs prompt v2 on agent B". Each contestant here
is a prompt (a Langfuse version or label of any prompt, or literal text) applied to one agent of the fleet, optionally
on its own model. Every contestant runs the same golden cases through ADK's LocalEvalService on the isolated SQLite
database, one after another (the prompts and models are process-wide settings of the fleet), and the results are
laid out side by side.

A contestant is a dict:

    {"name": "leave-v3", "agent": "leave", "prompt": "leave-subagent", "version": 3}
    {"agent": "root", "label": "gepa-optimized"}            # prompt defaults to the agent's own Langfuse prompt
    {"agent": "policy", "text": "You answer policy questions ...", "model": "groq/openai/gpt-oss-120b"}

Nothing needs to be optimised: any version, label or text can be compared with any other.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from app.evaluations.adk_expectations import to_eval_set
from app.evaluations.adk_support import _iter_agents, run_adk_evaluation
from app.optimization.adk_grid import _aggregate, default_item_ids, resolve_prompt_text
from app.optimization.metric import composite, eval_config_for
from app.optimization.runtime import to_adk_instruction

logger = logging.getLogger(__name__)

ROOT_KEYS = {"root", "hr_root_orchestrator", "orchestrator"}
# Each agent's own Langfuse prompt, used when a contestant names an agent but no prompt.
DEFAULT_PROMPT_FOR = {
    "root": "peopleops-root-orchestrator",
    "leave": "leave-subagent",
    "timesheet": "timesheet-subagent",
    "health": "health-subagent",
    "policy": "policy-rag-subagent",
    "zoho": "zoho-subagent",
}
NOISE_MARGIN = 0.05  # composite differences smaller than this are not distinguishable with a handful of cases


class CompareConfigError(ValueError):
    def __init__(self, problems: List[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _short(agent_name: str) -> str:
    return agent_name.removesuffix("_agent").removeprefix("hr_")


def find_agent(root_agent: Any, key: str) -> Any:
    """Resolve 'leave' / 'leave_agent' / 'root' to the agent object in the fleet."""
    wanted = (key or "root").strip().lower()
    if wanted in ROOT_KEYS:
        return root_agent
    agents = list(_iter_agents(root_agent))
    for agent in agents:
        name = str(getattr(agent, "name", "")).lower()
        if wanted in (name, _short(name), name.removesuffix("_agent")):
            return agent
    raise CompareConfigError([f"unknown agent '{key}'; choose one of: root, " + ", ".join(sorted(_short(a.name) for a in agents if a is not root_agent))])


def parse_contestant_spec(spec: str) -> Dict[str, Any]:
    """'agent=leave,prompt=leave-subagent,version=3,model=openai/gpt-4o-mini' -> dict. Text may not contain commas; use --config for that."""
    out: Dict[str, Any] = {}
    for part in spec.split(","):
        key, sep, value = part.partition("=")
        if not sep or not key.strip():
            raise CompareConfigError([f"bad contestant '{spec}': write key=value pairs separated by commas"])
        out[key.strip()] = value.strip()
    return out


def normalize_contestants(raw: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    problems: List[str] = []
    contestants: List[Dict[str, Any]] = []
    if len(raw) < 2:
        raise CompareConfigError(["give at least two contestants to compare"])
    for index, spec in enumerate(raw, start=1):
        agent = str(spec.get("agent") or "root").strip().lower()
        sources = [k for k in ("version", "label", "text") if spec.get(k) not in (None, "")]
        if len(sources) > 1:
            problems.append(f"contestant {index}: give only one of version, label or text (got {', '.join(sources)})")
            continue
        variant: Dict[str, Any]
        if "text" in sources:
            variant = {"text": str(spec["text"])}
        elif "version" in sources:
            try:
                variant = {"version": int(str(spec["version"]).lower().lstrip("v"))}
            except ValueError:
                problems.append(f"contestant {index}: version must be a number such as 3 or v3")
                continue
        else:
            variant = {"label": str(spec.get("label") or "live")}
        prompt_name = str(spec.get("prompt") or DEFAULT_PROMPT_FOR.get(agent.removesuffix("_agent").removeprefix("hr_"), ""))
        if "text" not in variant and not prompt_name:
            problems.append(f"contestant {index}: no Langfuse prompt for agent '{agent}'; pass prompt=<name>")
            continue
        described = variant.get("text", "")[:18] + "..." if "text" in variant else (f"v{variant['version']}" if "version" in variant else variant["label"])
        contestants.append({
            "name": str(spec.get("name") or f"{agent}:{described}"),
            "agent": agent, "prompt_name": prompt_name, "variant": variant, "model": spec.get("model") or None,
        })
    if problems:
        raise CompareConfigError(problems)
    names = [c["name"] for c in contestants]
    for i, name in enumerate(names):  # two contestants may legitimately look alike (e.g. same label on two models)
        if names.count(name) > 1:
            contestants[i]["name"] = f"{name}#{i + 1}"
    return contestants


def pick_items(contestants: Sequence[Dict[str, Any]], root_agent: Any, explicit: Optional[List[str]], *, deterministic_only: bool,
               limit: Optional[int]) -> tuple[List[str], Optional[str]]:
    """Same cases for everyone. If all contestants target one specialist, use the cases that should reach it."""
    allowed = default_item_ids(deterministic_only=deterministic_only, include_mutating=False)
    if explicit:
        unknown = [i for i in explicit if i not in allowed]
        if unknown:
            raise CompareConfigError([f"cases not available (mutating or unknown): {', '.join(unknown)}"])
        items, note = list(explicit), None
    else:
        items, note = allowed, None
        targets = {id(a): a for a in (find_agent(root_agent, c["agent"]) for c in contestants)}  # ADK agents are unhashable
        if len(targets) == 1 and next(iter(targets.values())) is not root_agent:
            from app.optimization.common import load_cases

            name = next(iter(targets.values())).name
            routed = [c.test_id for c in load_cases(pool="deterministic" if deterministic_only else "golden") if c.expected_route == name]
            if routed:
                items, note = [i for i in allowed if i in routed], f"Used the {len(routed)} cases that should be handed to {name}."
            else:
                note = f"No golden case is expected to reach {name}; ran every case instead."
    if limit:
        items = items[:limit]
    if not items:
        raise CompareConfigError(["no cases to run"])
    return items, note


async def _run_cases(case_ids: List[str], evalset: str, eval_config: Dict[str, Any], root_agent: Any, retries: int, wait_sec: float) -> List[Any]:
    """Run the cases; re-run only the ones that errored (usually provider rate limits) after a cooldown."""
    def run(ids: List[str]):
        return run_adk_evaluation(to_eval_set(eval_set_id=f"prompt_compare_{evalset}", test_ids=ids), eval_config, root_agent=root_agent, test_ids=ids)

    results = {r.test_id: r for r in await run(case_ids)}
    for attempt in range(1, retries + 1):
        failed = [cid for cid, r in results.items() if composite(r) is None]
        if not failed:
            break
        logger.info("%d case(s) errored (%s...); retry %d/%d after %.0fs", len(failed), failed[0], attempt, retries, wait_sec)
        await asyncio.sleep(wait_sec)
        for r in await run(failed):
            results[r.test_id] = r
    return list(results.values())


async def run_prompt_comparison(
    raw_contestants: Sequence[Dict[str, Any]],
    *,
    root_agent: Any,
    items: Optional[List[str]] = None,
    limit: Optional[int] = None,
    evalset: str = "deterministic",
    metrics: str = "standard",
    judge: Optional[str] = None,
    retry_errors: int = 2,
    retry_wait_sec: float = 65.0,
) -> Dict[str, Any]:
    from app.agents.adk_fleet import refresh_adk_fleet_models, set_root_instruction_override
    from app.core.config import settings
    from app.core.llm_bridge import restore_model_state, set_active_model, snapshot_model_state

    contestants = normalize_contestants(raw_contestants)
    targets = {c["name"]: find_agent(root_agent, c["agent"]) for c in contestants}
    case_ids, items_note = pick_items(contestants, root_agent, items, deterministic_only=(evalset == "deterministic"), limit=limit)
    eval_config = eval_config_for(metrics, judge)

    saved_instructions = {id(a): (a, a.instruction) for a in _iter_agents(root_agent)}
    state = snapshot_model_state()
    started = time.time()
    results: List[Dict[str, Any]] = []
    try:
        for c in contestants:
            entry: Dict[str, Any] = {"name": c["name"], "agent": c["agent"], "prompt_name": c["prompt_name"] or "(literal text)",
                                     "prompt": c["variant"].get("version") or c["variant"].get("label") or "text", "model": c["model"] or "default"}
            try:
                if "text" in c["variant"]:
                    raw_text, version = c["variant"]["text"], None
                else:
                    raw_text, version = resolve_prompt_text(c["prompt_name"], c["variant"])
                text = to_adk_instruction(raw_text)
                entry["resolved_version"] = version
                entry["prompt_chars"] = len(text)
                entry["prompt_text"] = raw_text
                refresh_adk_fleet_models(set_active_model(c["model"]))
                for agent, original in saved_instructions.values():   # every contestant starts from the same untouched fleet
                    agent.instruction = original
                target = targets[c["name"]]
                if target is root_agent:
                    set_root_instruction_override(text)
                else:
                    set_root_instruction_override(None)
                    target.instruction = text
                run = await _run_cases(case_ids, evalset, eval_config, root_agent, retry_errors, retry_wait_sec)
            except Exception as exc:
                logger.warning("Contestant %s failed: %s", c["name"], exc)
                results.append({**entry, "status": "error", "error": str(exc)[:300]})
                continue
            aggregate = _aggregate(run)
            results.append({
                **entry, "status": "ok" if aggregate["composite"] is not None else "error", **aggregate,
                "cases": {r.test_id: {"score": composite(r), "status": r.status, "tools": [t["tool_name"] for t in r.actual_tool_use],
                                      "error": r.error} for r in run},
            })
    finally:
        restore_model_state(state)
        set_root_instruction_override(None)
        for agent, original in saved_instructions.values():
            agent.instruction = original
        refresh_adk_fleet_models(None)

    return _summarise(results, case_ids, items_note, {
        "evalset": evalset, "metrics_preset": metrics, "judge": judge or "default", "duration_sec": round(time.time() - started, 1),
        "warnings": (["MOCK_LLM_ENABLED=true: everything ran on the mock provider; scores say nothing about the real models."] if settings.MOCK_LLM_ENABLED else []),
    })


def _summarise(results: List[Dict[str, Any]], case_ids: List[str], items_note: Optional[str], meta: Dict[str, Any]) -> Dict[str, Any]:
    ok = [r for r in results if r["status"] == "ok"]
    # Rank on the cases EVERY contestant scored: an errored case (usually a rate limit) must not flatter or punish one side.
    common = [cid for cid in case_ids if ok and all((r["cases"].get(cid) or {}).get("score") is not None for r in ok)]
    for r in ok:
        scores = [r["cases"][cid]["score"] for cid in common]
        r["paired_composite"] = round(sum(scores) / len(scores), 3) if scores else None
    ranked = sorted((r for r in ok if r["paired_composite"] is not None), key=lambda r: (r["paired_composite"], r["pass_rate_percent"]), reverse=True)
    errored = sum(r.get("errored_cases", 0) for r in ok) + sum(1 for r in results if r["status"] != "ok")
    reliable = bool(ranked) and len(ranked) == len(results) and errored == 0
    verdict: Dict[str, Any] = {"winner": None, "margin": None, "within_noise": None, "reliable": reliable, "compared_cases": len(common)}
    if ranked:
        verdict["winner"] = ranked[0]["name"]
        if len(ranked) > 1:
            verdict["margin"] = round(ranked[0]["paired_composite"] - ranked[1]["paired_composite"], 3)
            verdict["within_noise"] = abs(verdict["margin"]) < NOISE_MARGIN
    head_to_head: Optional[Dict[str, Any]] = None
    if len(ranked) >= 2:  # case-by-case record of the top two on the shared cases
        a, b = ranked[0], ranked[1]
        record = {"a": a["name"], "b": b["name"], "a_wins": 0, "b_wins": 0, "ties": 0}
        for cid in common:
            sa, sb = a["cases"][cid]["score"], b["cases"][cid]["score"]
            if abs(sa - sb) < 1e-9:
                record["ties"] += 1
            elif sa > sb:
                record["a_wins"] += 1
            else:
                record["b_wins"] += 1
        head_to_head = record
    status = "compare_failed" if not ok else ("compare_complete" if reliable else "compare_partial")
    return {"status": status, "engine": "google-adk", "cases": case_ids, "cases_note": items_note, "contestants": results,
            "ranking": [r["name"] for r in ranked], "verdict": verdict, "head_to_head": head_to_head, **meta}


def to_markdown(report: Dict[str, Any]) -> str:
    fmt = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
    contestants, v = report["contestants"], report["verdict"]
    lines = [f"# Prompt comparison ({len(contestants)} contestants, {len(report['cases'])} cases)", "",
             f"Metrics `{report['metrics_preset']}`, judge `{report['judge']}`, eval set `{report['evalset']}`, {report['duration_sec']}s.", ""]
    if report.get("cases_note"):
        lines += [report["cases_note"], ""]
    lines += ["| contestant | agent | prompt | model | score (shared cases) | scored cases | pass rate | latency ms |", "|---|---|---|---|---|---|---|---|"]
    for r in contestants:
        ver = f" v{r['resolved_version']}" if r.get("resolved_version") else ""
        label = f"{r['prompt_name']} ({r['prompt']}{ver})" if r["prompt_name"] != "(literal text)" else "literal text"
        win = " **(winner)**" if r["name"] == v["winner"] and v["reliable"] else ""
        if r["status"] != "ok":
            lines.append(f"| {r['name']} | {r['agent']} | {label} | {r['model']} | FAILED: {r.get('error')} | | | |")
        else:
            lines.append(f"| {r['name']}{win} | {r['agent']} | {label} | {r['model']} | {fmt(r.get('paired_composite'))} | "
                         f"{r['scored_cases']}/{r['scored_cases'] + r['errored_cases']} | {r['pass_rate_percent']}% | {r['average_latency_ms'] or 'n/a'} |")
    ok = [r for r in contestants if r["status"] == "ok"]
    if ok:
        names = sorted({m for r in ok for m in r["metrics"]})
        lines += ["", "## Per-metric averages (every case each contestant scored)", "", "| metric | " + " | ".join(r["name"] for r in ok) + " |", "|---|" + "---|" * len(ok)]
        for m in names:
            lines.append(f"| {m} | " + " | ".join(fmt(r["metrics"].get(m)) for r in ok) + " |")
        lines += ["", "## Case by case (composite score, tools the agent called)", "", "| case | " + " | ".join(r["name"] for r in ok) + " |", "|---|" + "---|" * len(ok)]
        for cid in report["cases"]:
            cells = []
            for r in ok:
                c = r["cases"].get(cid) or {}
                cells.append("ERROR (not scored)" if c.get("score") is None else f"{c['score']:.2f} ({', '.join(c.get('tools') or []) or 'no tools'})")
            lines.append(f"| {cid} | " + " | ".join(cells) + " |")
    lines.append("")
    h = report.get("head_to_head")
    if not v["winner"]:
        lines.append("**No result:** no case was scored by every contestant.")
    elif not v["reliable"]:
        lines.append(f"**Inconclusive.** Some cases errored (see above), so only the {v['compared_cases']} case(s) every contestant scored were compared; "
                     f"on those, {v['winner']} leads" + (f" by {v['margin']:+.3f}" if v["margin"] is not None else "") + ". Re-run, raise `--retry-errors`, or use a model without rate limits.")
    else:
        noise = " That gap is within noise for this few cases, so treat it as a tie." if v["within_noise"] else ""
        margin = f" by {v['margin']:+.3f}" if v["margin"] is not None else ""
        lines.append(f"**Winner: {v['winner']}**{margin} on {v['compared_cases']} cases.{noise}")
    if h:
        lines.append(f"Head to head ({h['a']} vs {h['b']}) on shared cases: {h['a_wins']} won, {h['b_wins']} lost, {h['ties']} tied.")
    lines += [f"- warning: {w}" for w in report["warnings"]]
    return "\n".join(lines) + "\n"
