"""
问答功能 Prompt 模板
"""
from app.schemas.graph import KnowledgeGraph


def build_chat_prompt(graph: KnowledgeGraph, question: str) -> tuple[str, str]:
    """
    构建问答的 system_prompt 和 user_message
    """

    system_prompt = """你是一个知识渊博的 AI 助手。用户正在查看一个知识图谱，会基于图谱内容向你提问。
请基于图谱中的实体和关系给出准确、清晰的回答。

## 规则
1. 优先基于图谱中的信息回答。
2. 图谱信息不足以回答时，可以结合你自身的知识补充，但要注明。
3. 回答简洁明了，适合学习场景。
4. 如果问"总结"或"概述"，用 3~5 句话概括图谱内容。"""

    # 把当前图谱转成文本描述
    node_text = "\n".join(
        f"  - [{n.category}] {n.name} (id: {n.id})"
        for n in graph.nodes
    )
    edge_text = "\n".join(
        f"  - {e.source} → {e.target}: {e.label}"
        for e in graph.edges
    )

    user_message = f"""## 当前知识图谱

### 节点（{len(graph.nodes)} 个）
{node_text if node_text else "（暂无节点）"}

### 关系（{len(graph.edges)} 条）
{edge_text if edge_text else "（暂无关系）"}

### 用户问题
{question}"""

    return system_prompt, user_message
