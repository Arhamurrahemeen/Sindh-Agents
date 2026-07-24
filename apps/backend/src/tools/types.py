import logging
from dataclasses import dataclass
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


@dataclass
class ToolContext:
    # tools_spec.md §0.1 — never pass sme_id as a direct tool arg, always via context.
    # message_id isn't in the doc's own listed context fields, but order_intents.message_id
    # (db_schema.md §1.11) is a NOT NULL FK to the triggering buyer message — added here
    # since record_order_intent can't satisfy that constraint without it.
    # buyer_id: same reasoning, found live — the planner LLM has no way to know the
    # real buyer_id UUID from conversation text and hallucinated a placeholder
    # ("current buyer") when asked to fill lookup_buyer_history's buyer_id field.
    # The orchestrator now overrides that field from context instead of trusting
    # the planner's guess.
    sme_id: str
    agent_id: str
    conversation_id: str
    buyer_id: str
    message_id: str
    request_id: str
    db: AsyncSession
    logger: logging.Logger


class ToolSuccess(BaseModel, Generic[T]):
    ok: Literal[True] = True
    data: T


class ToolNotFound(BaseModel):
    ok: Literal[False] = False
    reason: Literal["not_found"] = "not_found"
    detail: str


class ToolDegraded(BaseModel):
    ok: Literal[False] = False
    reason: Literal["degraded"] = "degraded"
    detail: str
