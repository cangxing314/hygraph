"""
问答服务 - 基于当前图谱上下文回答用户问题
"""
import logging

from app.ai.hy3_client import hy3_client
from app.ai.prompts.chat_prompts import build_chat_prompt
from app.schemas.graph import KnowledgeGraph

logger = logging.getLogger(__name__)


class ChatService:
    """知识问答服务"""

    async def ask_stream(self, graph: KnowledgeGraph, question: str):
        """
        流式问答：基于图谱内容回答，逐字返回

        graph: 前端传来的当前图谱（含所有已展开节点）
        question: 用户的问题
        """
        system_prompt, user_message = build_chat_prompt(graph, question)

        # 调用 Hy3 流式接口
        stream = await hy3_client.client.chat.completions.create(
            model=hy3_client.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            stream=True,
        )

        # 逐块 yield 文本
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


# 全局单例
chat_service = ChatService()
