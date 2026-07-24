import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.orchestrator import process_buyer_message
from src.db import async_session
from src.repositories.agent_repository import AgentRepository
from src.repositories.audit_repository import AgentReplyResult, AuditRepository, ToolCallRecord
from src.repositories.buyer_repository import BuyerRepository
from src.repositories.conversation_repository import ConversationRepository
from src.repositories.message_repository import MessageRepository
from src.repositories.sme_repository import SmeRepository
from src.services.clock import now_in_karachi
from src.services.groq_client import GroqChatCompleter

CORPUS_PATH = Path(__file__).parent / "corpus.jsonl"
PILOT_SME_PHONE = "+923005551234"
HARD_FAIL_THRESHOLD_PCT = 80.0

# maps a case's buyer_key to the seeded wa_id — must match apps/backend/seeds/pilot_sme.py
SEEDED_BUYER_WA_IDS = {
    "ali-traders": "seed-ali-traders",
    "saleem-fabrics": "seed-saleem-fabrics",
    "khan-garments": "seed-khan-garments",
}


@dataclass
class EvalCase:
    id: str
    buyer_key: str
    buyer_message: str
    expect_tool_calls: list[str]
    expect_verbatim: list[str]
    forbid_substrings: list[str]
    dynamic_check: str | None


@dataclass
class EvalCaseResult:
    case_id: str
    passed: bool
    reasons: list[str] = field(default_factory=list)
    reply_text: str = ""


def load_corpus() -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        cases.append(
            EvalCase(
                id=raw["id"],
                buyer_key=raw["buyer_key"],
                buyer_message=raw["buyer_message"],
                expect_tool_calls=raw["expect_tool_calls"],
                expect_verbatim=raw["expect_verbatim"],
                forbid_substrings=raw["forbid_substrings"],
                dynamic_check=raw["dynamic_check"],
            )
        )
    return cases


def _check_dynamic(dynamic_check: str | None) -> str | None:
    if dynamic_check == "current_weekday":
        return now_in_karachi().strftime("%A")
    if dynamic_check is None:
        return None
    raise ValueError(f"unknown dynamic_check: {dynamic_check}")


async def _resolve_buyer_id(db: AsyncSession, sme_id: str, case: EvalCase) -> str:
    if case.buyer_key == "fresh":
        wa_id = f"eval-{case.id}"
        name = f"Eval Buyer ({case.id})"
    else:
        wa_id = SEEDED_BUYER_WA_IDS[case.buyer_key]
        name = case.buyer_key
    buyer = await BuyerRepository(db).get_or_create(sme_id, wa_id, name)
    return buyer.id


async def run_case(case: EvalCase, logger: logging.Logger) -> EvalCaseResult:
    async with async_session() as db:
        sme = await SmeRepository(db).get_by_phone(PILOT_SME_PHONE)
        if sme is None:
            raise RuntimeError("Pilot SME not seeded — run `python -m seeds.pilot_sme` first")
        agents = await AgentRepository(db).list_for_sme(sme.id)
        if not agents:
            raise RuntimeError("Pilot agent not seeded")
        agent_id = agents[0].id

        buyer_id = await _resolve_buyer_id(db, sme.id, case)
        conversation = await ConversationRepository(db).get_or_create(sme.id, buyer_id, agent_id)
        buyer_message = await MessageRepository(db).insert_buyer_message(
            sme.id, conversation.id, case.buyer_message, now_in_karachi()
        )
        await db.commit()

        captured_tool_calls: list[ToolCallRecord] = []
        real_writer = AuditRepository(db).write_agent_reply_with_audit

        async def spy_audit_writer(
            sme_id: str,
            conversation_id: str,
            buyer_message_id: str,
            parsed_intent: str,
            tool_calls: list[ToolCallRecord],
            agent_reply_text: str,
            model: str,
            total_latency_ms: int,
        ) -> AgentReplyResult:
            captured_tool_calls.extend(tool_calls)
            return await real_writer(
                sme_id=sme_id,
                conversation_id=conversation_id,
                buyer_message_id=buyer_message_id,
                parsed_intent=parsed_intent,
                tool_calls=tool_calls,
                agent_reply_text=agent_reply_text,
                model=model,
                total_latency_ms=total_latency_ms,
            )

        result = await process_buyer_message(
            db=db,
            completer=GroqChatCompleter(),
            sme_id=sme.id,
            agent_id=agent_id,
            conversation_id=conversation.id,
            buyer_id=buyer_id,
            buyer_message_id=buyer_message.id,
            buyer_message_text=case.buyer_message,
            conversation_history=[],
            logger=logger,
            audit_writer=spy_audit_writer,
        )

    reasons: list[str] = []
    called_tool_names = {tc.name for tc in captured_tool_calls}

    missing_tools = set(case.expect_tool_calls) - called_tool_names
    if missing_tools:
        reasons.append(f"expected tool(s) not called: {sorted(missing_tools)}")

    missing_verbatim = [s for s in case.expect_verbatim if s not in result.reply_text]
    if missing_verbatim:
        reasons.append(f"missing verbatim substring(s): {missing_verbatim}")

    leaked = [s for s in case.forbid_substrings if s in result.reply_text]
    if leaked:
        reasons.append(f"forbidden substring(s) present: {leaked}")

    dynamic_expected = _check_dynamic(case.dynamic_check)
    if dynamic_expected is not None and dynamic_expected not in result.reply_text:
        reasons.append(f"dynamic check failed: expected {dynamic_expected!r} in reply")

    return EvalCaseResult(
        case_id=case.id, passed=not reasons, reasons=reasons, reply_text=result.reply_text
    )


async def run_all(logger: logging.Logger) -> list[EvalCaseResult]:
    results = []
    for case in load_corpus():
        try:
            results.append(await run_case(case, logger))
        except (
            Exception
        ) as exc:  # noqa: BLE001 — a crashed case is a failed case, not a harness bug
            results.append(
                EvalCaseResult(case_id=case.id, passed=False, reasons=[f"crashed: {exc}"])
            )
    return results


def summarize(results: list[EvalCaseResult]) -> tuple[float, bool]:
    passed = sum(1 for r in results if r.passed)
    pct = (passed / len(results)) * 100 if results else 0.0
    return pct, pct >= HARD_FAIL_THRESHOLD_PCT
