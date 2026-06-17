"""Build the Hype Crew — 2 LLM agents only (post V3-integration refactor).

Architecture after fixes:
- Crew (2 agents — creative LLM work). Model = settings.model_fast / model_smart
  (prod default: openrouter/google/gemini-3-flash-preview; HYPE_MODEL_* ile override):
    TrendScout (settings.model_fast)   → pick best trend, filter politics-adjacent
    Planner    (settings.model_smart)  → pick etki/karakter/uzunluk + brief
- Flow handles (deterministic, no Hype-Crew LLM):
    write_via_typehype → calls TypeHype /api/internal/generate-tweet (proven V3 prompt)
    run_compliance    → dedup_check + forbidden_topics + hard_rules + 1 mini LLM voice critic
    publish_branch    → Postiz schedule + daily_drafts row

Why this layout:
- Writer / Compliance / Publisher don't need LLM agents — they're deterministic
  orchestration. Pulling them out of Crew avoids CrewAI Process.sequential running
  unnecessary stages AND lets us reuse TypeHype's tested V3 prompt.
- Cost dropped ~14x (was ~$0.22/run with custom Writer prompt, now ~$0.016).
"""
from typing import Optional

from crewai import Crew, Task, Process

from agents import build_trendscout, build_planner
from schemas import TrendScoutOutput, PlannerOutput
from tools import format_memory_context, load_account_config


# ─── Task description templates ────────────────────────────────────────────


TASK_TRENDSCOUT = """
For account_id={account_id}, query trends and select ONE trend that is:
- VIP source (is_vip=true) OR score >= 90
- Fits the creator's topics_focus: {topics_focus}
- Not in forbidden_topics: {forbidden_topics}
- Has a credible angle the creator could take

Use the `query_trends` tool with account_id={account_id}, min_score=90, vip_only=False.
The tool defaults to excluding News/Politics/Entertainment categories — keep that.

═══ EDITORIAL LEAD CONSTRAINT (when set) ═══
{editorial_lead_directive}
═══════════════════════════════════════════

Review the returned trends. Pick ONE or set passed=False if nothing qualifies.

If you pick a trend, call `mark_trend_processed` to log it.

Strictly reject politics-adjacent topics (country-vs-country rivalry, trade wars,
sanctions, government policies) when 'politics' is in forbidden_topics — see your
backstory for the full detection rules.

Return TrendScoutOutput. If no trend qualifies, set passed=False with skip_reason.
""".strip()


EDITORIAL_LEAD_DIRECTIVE = (
    "An editor's-desk pass has SELECTED THIS TREND as today's lead:\n"
    "  trend_id: {trend_id}\n"
    "  topic:    {topic}\n"
    "  editor's reason: {operator_sentence}\n"
    "\n"
    "You MUST score and enrich THIS specific trend. Look it up via\n"
    "query_trends, find the row with this trend_id, then emit TrendScoutOutput\n"
    "for it (set passed=True unless persona-gate would reject it). Do NOT pick\n"
    "a different trend. Your job in this run is to ENRICH the editor's pick\n"
    "with content_type / rubric breakdown / video_worthy — the editorial\n"
    "selection has already happened.\n"
)
EDITORIAL_LEAD_DIRECTIVE_EMPTY = (
    "(no editor's-desk pick this firing — fall through to legacy rubric "
    "selection)"
)


TASK_PLANNER = """
Given the selected trend (from previous step), pick the optimal V3 parameters:
- etki: which effect (patlassin/konustursun/ogretsin/iz_biraksin/shitpost)
- karakter: which persona (uzman/otorite/iceriden/mentalist/haberci)
- uzunluk: which length (micro/punch/spark/storm)
- hook_type: which hook style (curiosity/first-person/result/contrast/question/story)
- brief: detailed brief (what to write, how to open, what angle) — this becomes
  the additional_context that TypeHype's V3 generation uses verbatim.
- angle: the creator's unique POV on this trend
- target_engagement: replies/bookmarks/reposts/mixed

CRITICAL: Use semantic_recall tool to find similar past wins (approved_drafts).
Mirror what worked. Avoid patterns in rejected_drafts memory.

After this step, Flow will call TypeHype's proven V3 generator with these
parameters (no Hype Crew LLM here). So your brief MUST be precise and self-contained.

Return PlannerOutput with full reasoning.
""".strip()


# ─── Crew factory ──────────────────────────────────────────────────────────


def build_content_crew(account_id: str,
                         editorial_lead: Optional[dict] = None) -> Crew:
    """Build a fresh 2-agent Hype Crew for one account run.

    Each invocation:
    1. Loads account config (no caching — always fresh).
    2. Loads current memory snapshot (markdown injection).
    3. Builds 2 agents with account-scoped state.
    4. Wires 2 sequential tasks with Pydantic outputs.

    Writer/Compliance/Publisher are NOT in Crew — they live in Flow as
    deterministic non-LLM steps (or TypeHype-delegated for Writer).
    """
    config_fn = load_account_config.func if hasattr(load_account_config, "func") else load_account_config
    config = config_fn(account_id)
    memory_context = format_memory_context(account_id)

    trendscout = build_trendscout(config)
    planner = build_planner(config, memory_context)

    forbidden_list = config.get("forbidden_topics") or []

    if editorial_lead and editorial_lead.get("trend_id"):
        editorial_directive = EDITORIAL_LEAD_DIRECTIVE.format(
            trend_id=editorial_lead.get("trend_id"),
            topic=(editorial_lead.get("topic") or "")[:200],
            operator_sentence=(editorial_lead.get("operator_sentence")
                                or editorial_lead.get("reason") or "")[:400],
        )
    else:
        editorial_directive = EDITORIAL_LEAD_DIRECTIVE_EMPTY

    task_scout = Task(
        description=TASK_TRENDSCOUT.format(
            account_id=account_id,
            topics_focus=", ".join(config.get("topics_focus") or []) or "general",
            forbidden_topics=", ".join(forbidden_list) or "none",
            editorial_lead_directive=editorial_directive,
        ),
        agent=trendscout,
        expected_output="A TrendScoutOutput JSON object",
        output_pydantic=TrendScoutOutput,
    )

    task_plan = Task(
        description=TASK_PLANNER,
        agent=planner,
        expected_output="A PlannerOutput JSON object",
        output_pydantic=PlannerOutput,
        context=[task_scout],
    )

    return Crew(
        agents=[trendscout, planner],
        tasks=[task_scout, task_plan],
        process=Process.sequential,
        verbose=True,
        memory=False,
    )
