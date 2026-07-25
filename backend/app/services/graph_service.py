"""
图谱生成业务逻辑
编排 Hy3 调用 → 解析 JSON → 返回结构化数据
"""
import json
import logging

from app.ai.hy3_client import hy3_client
from app.ai.prompts.graph_prompts import GRAPH_GENERATION_PROMPT, NODE_EXPANSION_PROMPT
from app.schemas.graph import KnowledgeGraph, GraphNode, GraphEdge, ExistingNode

logger = logging.getLogger(__name__)


class GraphService:
    """知识图谱服务"""

    async def generate(self, topic: str) -> KnowledgeGraph:
        """
        根据主题生成知识图谱
        1. 调用 Hy3
        2. 解析 JSON
        3. 校验并返回
        """
        # 调用 Hy3，要求返回 JSON
        raw_json = await hy3_client.chat_json(
            system_prompt=GRAPH_GENERATION_PROMPT,
            user_message=f"请为我生成关于「{topic}」的知识图谱。",
        )

        # 解析 JSON
        graph = self._parse_graph(raw_json)
        return graph

    async def expand(self, node_id: str, node_name: str, existing_nodes: list[ExistingNode]) -> KnowledgeGraph:
        """
        延伸某个节点，生成子图谱
        新子节点会与目标节点相连，也会与有关联的已有节点相连
        """
        # 把已有节点的 id+名称告诉 Hy3：既避免重复，也让它能把新节点关联到旧节点上
        existing_text = "、".join(
            f"{n.name}(id:{n.id})" for n in existing_nodes
        ) or "（暂无）"
        context = (
            f"目标节点：{node_name}(id:{node_id})。\n"
            f"已有节点：{existing_text}。\n"
            "请围绕目标节点生成子节点，不要重复已有节点；"
            "如果某个子节点与已有节点存在明确关系，请同时生成对应的边。"
        )

        raw_json = await hy3_client.chat_json(
            system_prompt=NODE_EXPANSION_PROMPT,
            user_message=context,
        )

        # 延伸时，边可以指向：新节点、目标节点、任意已有节点
        # 所以把所有已有节点 id 都加入"可信 id"白名单
        known_ids = {n.id for n in existing_nodes} | {node_id}
        graph = self._parse_graph(raw_json, known_node_ids=known_ids)
        return graph

    def _parse_graph(self, raw_json: str, known_node_ids: set[str] | None = None) -> KnowledgeGraph:
        """
        解析 Hy3 返回的 JSON 字符串为 KnowledgeGraph 对象

        参数:
            raw_json: Hy3 返回的 JSON 字符串
            known_node_ids: 已经存在的节点 id（用于延伸场景，让边验证通过）
        """
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}\n原始内容: {raw_json[:300]}")
            return KnowledgeGraph(nodes=[], edges=[])

        # 提取节点
        nodes = []
        for n in data.get("nodes", []):
            nodes.append(GraphNode(
                id=n.get("id", "unknown"),
                name=n.get("name", n.get("id", "未知")),
                category=n.get("category", "概念"),
            ))

        # 提取边：允许边的两端是「新节点」或「已知节点」
        all_node_ids = {n.id for n in nodes} | (known_node_ids or set())
        edges = []
        for e in data.get("edges", []):
            source = e.get("source", "")
            target = e.get("target", "")
            if source in all_node_ids and target in all_node_ids:
                edges.append(GraphEdge(
                    source=source,
                    target=target,
                    label=e.get("label", "相关"),
                ))

        logger.info(f"解析图谱成功：{len(nodes)} 个节点，{len(edges)} 条边")
        return KnowledgeGraph(nodes=nodes, edges=edges)


# 全局单例
graph_service = GraphService()
