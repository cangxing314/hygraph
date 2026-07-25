"""
测试 Hy3 API 是否连通
运行方式：在 backend 目录下执行
    py -m scripts.test_hy3
"""
import sys
import asyncio

# 把 backend 目录加入 Python 路径
sys.path.insert(0, ".")

from app.ai.hy3_client import hy3_client


async def main():
    print("=" * 50)
    print("测试 Hy3 API 连接...")
    print("=" * 50)

    # 测试 1：简单对话
    print("\n【测试 1】简单对话：")
    result = await hy3_client.chat(
        system_prompt="你是知识图谱助手，回答简洁明了。",
        user_message="用一句话介绍什么是 Transformer（深度学习领域）",
    )
    print(f"回复: {result}")

    # 测试 2：强制返回 JSON
    print("\n【测试 2】JSON 输出：")
    result = await hy3_client.chat_json(
        system_prompt="你是一个 JSON 生成器，只输出 JSON，不要加任何其他文字。",
        user_message='输出一个包含"name"和"age"两个字段的 JSON 对象',
    )
    print(f"回复: {result}")

    print("\n✅ 测试通过！Hy3 API 连接正常")


if __name__ == "__main__":
    asyncio.run(main())