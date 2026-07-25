"""
问答相关的 API 路由（SSE 流式）
"""
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.graph import KnowledgeGraph
from app.services.chat_service import chat_service
from app.db.database import AsyncSessionLocal, get_db
from app.db.dal import message_dal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["知识问答"])


class ChatRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., min_length=1, description="用户问题")
    graph: KnowledgeGraph = Field(..., description="当前图谱完整数据")
    graph_id: int | None = Field(default=None, description="当前图谱的保存 id（用于问答历史入库）")


async def _save_message(graph_id: int | None, role: str, content: str):
    """静默保存一条消息，失败只记日志，绝不影响问答主流程"""
    if not graph_id or not content:
        return
    try:
        async with AsyncSessionLocal() as db:
            await message_dal.add(db, graph_id, role, content)
    except Exception as e:
        logger.warning(f"问答消息保存失败（已忽略）: {e}")


@router.post("/ask")
async def ask_question(req: ChatRequest):
    """
    基于图谱上下文回答用户问题（SSE 流式输出）
    传 {"question": "...", "graph": {...}, "graph_id": 1} → 逐字返回答案
    问题和完整回答都会存进 messages 表
    """
    async def event_stream():
        """SSE 事件生成器"""
        # 1. 先存用户的问题
        await _save_message(req.graph_id, "user", req.question)

        # 2. 流式输出 AI 回答，同时拼完整文本
        full_answer: list[str] = []
        try:
            async for token in chat_service.ask_stream(
                graph=req.graph,
                question=req.question,
            ):
                full_answer.append(token)
                # SSE 格式：data: {...}\n\n
                yield f"data: {json.dumps({'token': token})}\n\n"

            # 发送结束信号
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        # 3. 流结束后把完整回答存库
        await _save_message(req.graph_id, "assistant", "".join(full_answer))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@router.get("/history/{graph_id}")
async def chat_history(graph_id: int, db: AsyncSession = Depends(get_db)):
    """
    取出某个图谱的全部问答历史（按时间正序）
    """
    try:
        items = await message_dal.list_by_graph(db, graph_id)
        return {"success": True, "items": items}
    except Exception as e:
        return {"success": False, "items": [], "message": str(e)}
