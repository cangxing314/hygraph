"""
数据访问层 (Data Access Layer)
封装所有数据库的增删查改操作
"""
import logging
from datetime import datetime

from sqlalchemy import select, desc, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GraphRecord, NodeRecord, EdgeRecord, MessageRecord
from app.schemas.graph import KnowledgeGraph, GraphNode, GraphEdge

logger = logging.getLogger(__name__)


class GraphDAL:
    """图谱数据访问层"""

    # ============================================================
    # 保存图谱
    # ============================================================
    async def save(self, db: AsyncSession, topic: str, graph: KnowledgeGraph) -> int:
        """保存一个完整图谱到数据库，返回图谱 id"""
        # 1. 创建图谱记录
        record = GraphRecord(topic=topic)
        db.add(record)
        await db.flush()  # flush 让 record.id 立即生成

        # 2. 批量插入节点
        for n in graph.nodes:
            db.add(NodeRecord(
                graph_id=record.id,
                node_key=n.id,
                name=n.name,
                category=n.category,
            ))

        # 3. 批量插入边
        for e in graph.edges:
            db.add(EdgeRecord(
                graph_id=record.id,
                source_key=e.source,
                target_key=e.target,
                label=e.label,
            ))

        await db.commit()
        logger.info(f"图谱已保存: id={record.id}, topic={topic}, {len(graph.nodes)} 节点, {len(graph.edges)} 边")
        return record.id


    # ============================================================
    # 覆盖更新已有图谱（自动保存同步用）
    # ============================================================
    async def update(self, db: AsyncSession, graph_id: int, graph: KnowledgeGraph) -> bool:
        """用最新图谱内容覆盖指定记录（节点和边全量替换），图谱不存在返回 False"""
        result = await db.execute(
            select(GraphRecord).where(GraphRecord.id == graph_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return False

        # 1. 清掉旧的节点和边
        await db.execute(sql_delete(EdgeRecord).where(EdgeRecord.graph_id == graph_id))
        await db.execute(sql_delete(NodeRecord).where(NodeRecord.graph_id == graph_id))

        # 2. 写入最新内容
        for n in graph.nodes:
            db.add(NodeRecord(
                graph_id=graph_id,
                node_key=n.id,
                name=n.name,
                category=n.category,
            ))
        for e in graph.edges:
            db.add(EdgeRecord(
                graph_id=graph_id,
                source_key=e.source,
                target_key=e.target,
                label=e.label,
            ))

        await db.commit()
        logger.info(f"图谱已同步更新: id={graph_id}, {len(graph.nodes)} 节点, {len(graph.edges)} 边")
        return True


    # ============================================================
    # 列出所有已保存的图谱（概要信息）
    # ============================================================
    async def list_all(self, db: AsyncSession) -> list[dict]:
        """返回所有图谱的简要信息"""
        result = await db.execute(
            select(GraphRecord).order_by(desc(GraphRecord.created_at)).limit(20)
        )
        records = result.scalars().all()

        return [
            {
                "id": r.id,
                "topic": r.topic,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in records
        ]


    # ============================================================
    # 加载单个图谱（完整节点 + 边）
    # ============================================================
    async def load(self, db: AsyncSession, graph_id: int) -> KnowledgeGraph | None:
        """按 id 加载完整图谱"""
        # 查图谱记录
        result = await db.execute(
            select(GraphRecord).where(GraphRecord.id == graph_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return None

        # 查节点
        node_result = await db.execute(
            select(NodeRecord).where(NodeRecord.graph_id == graph_id)
        )
        node_records = node_result.scalars().all()

        # 查边
        edge_result = await db.execute(
            select(EdgeRecord).where(EdgeRecord.graph_id == graph_id)
        )
        edge_records = edge_result.scalars().all()

        # 转换为业务模型
        nodes = [
            GraphNode(id=n.node_key, name=n.name, category=n.category)
            for n in node_records
        ]
        edges = [
            GraphEdge(source=e.source_key, target=e.target_key, label=e.label)
            for e in edge_records
        ]

        logger.info(f"图谱已加载: id={graph_id}, {len(nodes)} 节点, {len(edges)} 边")
        return KnowledgeGraph(nodes=nodes, edges=edges)


    # ============================================================
    # 删除图谱
    # ============================================================
    async def delete(self, db: AsyncSession, graph_id: int) -> bool:
        """删除指定图谱"""
        result = await db.execute(
            select(GraphRecord).where(GraphRecord.id == graph_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            return False

        await db.execute(sql_delete(EdgeRecord).where(EdgeRecord.graph_id == graph_id))
        await db.execute(sql_delete(NodeRecord).where(NodeRecord.graph_id == graph_id))
        await db.execute(sql_delete(GraphRecord).where(GraphRecord.id == graph_id))
        await db.commit()
        logger.info(f"图谱已删除: id={graph_id}")
        return True


# 全局单例
graph_dal = GraphDAL()


# ============================================================
# 问答消息数据访问层
# ============================================================
class MessageDAL:
    """问答消息数据访问层"""

    async def add(self, db: AsyncSession, graph_id: int, role: str, content: str) -> None:
        """追加一条消息"""
        db.add(MessageRecord(graph_id=graph_id, role=role, content=content))
        await db.commit()

    async def list_by_graph(self, db: AsyncSession, graph_id: int) -> list[dict]:
        """按时间顺序取出某个图谱的全部问答"""
        result = await db.execute(
            select(MessageRecord)
            .where(MessageRecord.graph_id == graph_id)
            .order_by(MessageRecord.created_at, MessageRecord.id)
        )
        records = result.scalars().all()
        return [
            {
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in records
        ]


# 全局单例
message_dal = MessageDAL()
