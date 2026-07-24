from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.errors import ApiError
from src.middleware.auth import AuthSession, require_session
from src.repositories.agent_repository import AgentRepository
from src.repositories.conversation_repository import ConversationRepository
from src.repositories.message_repository import MessageRepository
from src.repositories.sme_repository import SmeRepository
from src.services.preview import truncate_preview

router = APIRouter()


class AgentItem(BaseModel):
    id: str
    name: str
    nameUrdu: str
    status: str
    messagesToday: int
    lastActive: str | None


class RecentConversationItem(BaseModel):
    id: str
    buyerName: str
    lastMessagePreview: str
    lastMessageAt: str
    unread: bool


class AgentsData(BaseModel):
    smeName: str
    ownerName: str
    agents: list[AgentItem]
    recentConversations: list[RecentConversationItem]


class AgentsResponse(BaseModel):
    ok: bool = True
    data: AgentsData


@router.get("")
async def list_agents_route(
    session: AuthSession = Depends(require_session),
    db: AsyncSession = Depends(get_db),
) -> AgentsResponse:
    sme = await SmeRepository(db).get_by_id(session.sme_id)
    if sme is None:
        raise ApiError(401, "AUTH_REQUIRED", "Session refers to a deleted SME")

    agent_repo = AgentRepository(db)
    message_repo = MessageRepository(db)
    agents = await agent_repo.list_for_sme(session.sme_id)

    agent_items = []
    for agent in agents:
        messages_today = await message_repo.count_today_for_agent(session.sme_id, agent.id)
        last_active = await message_repo.last_active_for_agent(session.sme_id, agent.id)
        agent_items.append(
            AgentItem(
                id=agent.id,
                name=agent.name,
                nameUrdu=agent.name_urdu,
                status=agent.status,
                messagesToday=messages_today,
                lastActive=last_active.isoformat() if last_active else None,
            )
        )

    recent = await ConversationRepository(db).list_recent(session.sme_id, limit=5)
    recent_items = [
        RecentConversationItem(
            id=r.id,
            buyerName=r.buyer_name,
            lastMessagePreview=truncate_preview(r.last_message_preview or ""),
            lastMessageAt=r.last_message_at.isoformat(),
            unread=r.unread,
        )
        for r in recent
    ]

    return AgentsResponse(
        data=AgentsData(
            smeName=sme.name,
            ownerName=sme.owner_name,
            agents=agent_items,
            recentConversations=recent_items,
        )
    )
