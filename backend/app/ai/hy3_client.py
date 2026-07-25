"""
Hy3 API 客户端
使用官方 OpenAI SDK（Hy3 兼容 OpenAI 协议）
"""
from openai import AsyncOpenAI
from app.core.config import settings


class Hy3Client:
    """Hy3 API 的单例客户端"""

    def __init__(self):
        # 用官方 AsyncOpenAI（兼容 Hy3 协议）
        self.client = AsyncOpenAI(
            api_key=settings.HY3_API_KEY,
            base_url=settings.HY3_BASE_URL,
            timeout=settings.HY3_TIMEOUT,
        )
        self.model = settings.HY3_MODEL

    async def chat(self, system_prompt: str, user_message: str) -> str:
        """
        普通对话，返回文本
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content

    async def chat_json(self, system_prompt: str, user_message: str) -> str:
        """
        强制 JSON 输出
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


# 全局单例
hy3_client = Hy3Client()