"""
ORM 模型定义
每个类对应 MySQL 中一张表
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.db.database import Base


# ============================================================
# 图谱记录表（存每次生成的知识图谱）
# ============================================================
class GraphRecord(Base):
    __tablename__ = "graphs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(200), nullable=False, comment="图谱主题")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    # 关联：一个图谱有多条节点记录和边记录
    nodes = relationship("NodeRecord", back_populates="graph", cascade="all, delete-orphan")
    edges = relationship("EdgeRecord", back_populates="graph", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Graph #{self.id}: {self.topic}>"


# ============================================================
# 节点记录表
# ============================================================
class NodeRecord(Base):
    __tablename__ = "graph_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graph_id = Column(Integer, ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    node_key = Column(String(100), nullable=False, comment="节点唯一标识（英文）")
    name = Column(String(200), nullable=False, comment="节点名称（中文）")
    category = Column(String(50), default="概念", comment="节点类别")

    graph = relationship("GraphRecord", back_populates="nodes")

    def __repr__(self):
        return f"<Node {self.node_key}: {self.name}>"


# ============================================================
# 边记录表
# ============================================================
class EdgeRecord(Base):
    __tablename__ = "graph_edges"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graph_id = Column(Integer, ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    source_key = Column(String(100), nullable=False, comment="起点节点 key")
    target_key = Column(String(100), nullable=False, comment="终点节点 key")
    label = Column(String(200), default="相关", comment="关系描述")

    graph = relationship("GraphRecord", back_populates="edges")

    def __repr__(self):
        return f"<Edge {self.source_key}→{self.target_key}: {self.label}>"


# ============================================================
# 问答消息表（挂在图谱下，图谱删除时一起删）
# ============================================================
class MessageRecord(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    graph_id = Column(Integer, ForeignKey("graphs.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, comment="角色：user / assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    created_at = Column(DateTime, default=datetime.now, comment="发送时间")

    def __repr__(self):
        return f"<Message #{self.id} [{self.role}] graph={self.graph_id}>"
