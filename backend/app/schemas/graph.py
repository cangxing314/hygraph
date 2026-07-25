"""
图谱相关的 Pydantic 数据模型
定义 API 请求和响应的数据结构
"""
from pydantic import BaseModel, Field


# ============================================================
# 图谱中的节点
# ============================================================
class GraphNode(BaseModel):
    """知识图谱中的一个节点（实体）"""
    id: str = Field(..., description="节点唯一标识（英文）")
    name: str = Field(..., description="节点显示名称（中文）")
    category: str = Field(default="概念", description="节点类别：概念/人物/技术/理论/应用")


# ============================================================
# 图谱中的边（关系）
# ============================================================
class GraphEdge(BaseModel):
    """知识图谱中的一条边（关系）"""
    source: str = Field(..., description="起点节点 id")
    target: str = Field(..., description="终点节点 id")
    label: str = Field(default="相关", description="关系描述")


# ============================================================
# 完整的知识图谱
# ============================================================
class KnowledgeGraph(BaseModel):
    """完整知识图谱 = 节点集合 + 边集合"""
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ============================================================
# API 请求
# ============================================================
class GraphGenerateRequest(BaseModel):
    """图谱生成请求"""
    topic: str = Field(..., min_length=1, max_length=200, description="知识主题")


class ExistingNode(BaseModel):
    """图谱中已存在的节点（延伸时发给后端，用于去重和关联）"""
    id: str = Field(..., description="已有节点 id")
    name: str = Field(default="", description="已有节点名称")


class NodeExpandRequest(BaseModel):
    """节点延伸请求"""
    node_id: str = Field(..., description="要延伸的节点 id")
    node_name: str = Field(..., description="要延伸的节点名称")
    existing_nodes: list[ExistingNode] = Field(default_factory=list, description="已有的节点列表，避免重复并用于关联")


# ============================================================
# API 响应
# ============================================================
class GraphResponse(BaseModel):
    """图谱生成/延伸的统一响应"""
    success: bool = True
    graph: KnowledgeGraph = Field(default_factory=KnowledgeGraph)
    message: str = ""
