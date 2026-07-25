"""
图谱相关的 API 路由
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.schemas.graph import (
    GraphGenerateRequest, NodeExpandRequest, GraphResponse, KnowledgeGraph,
)
from app.services.graph_service import graph_service
from app.db.dal import graph_dal
from app.db.database import get_db

router = APIRouter(prefix="/api/graph", tags=["知识图谱"])


# ---- 保存请求模型 ----
class GraphSaveRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=200)
    graph: KnowledgeGraph


# ============================================================
# 生成 & 延伸
# ============================================================
@router.post("/generate", response_model=GraphResponse)
async def generate_graph(req: GraphGenerateRequest):
    """
    根据主题生成知识图谱
    传 {"topic": "Transformer架构"} → 返回节点和边
    """
    try:
        graph = await graph_service.generate(topic=req.topic)

        if not graph.nodes:
            return GraphResponse(
                success=False,
                message="未能生成有效的知识图谱，请换个主题试试",
            )

        return GraphResponse(
            success=True,
            graph=graph,
            message=f"成功生成 {len(graph.nodes)} 个节点、{len(graph.edges)} 条边",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图谱生成失败：{str(e)}")


@router.post("/expand", response_model=GraphResponse)
async def expand_node(req: NodeExpandRequest):
    """
    点击节点后延伸子图谱
    传 {"node_id": "transformer", "node_name": "Transformer", "existing_nodes": ["..."]}
    → 返回该节点的新子节点和边
    """
    try:
        graph = await graph_service.expand(
            node_id=req.node_id,
            node_name=req.node_name,
            existing_nodes=req.existing_nodes,
        )

        if not graph.nodes:
            return GraphResponse(
                success=False,
                message=f"「{req.node_name}」暂无可延伸的子节点",
            )

        return GraphResponse(
            success=True,
            graph=graph,
            message=f"成功延伸 {len(graph.nodes)} 个子节点",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"节点延伸失败：{str(e)}")


# ============================================================
# 持久化：保存 / 列表 / 加载 / 删除
# ============================================================
@router.post("/save")
async def save_graph(req: GraphSaveRequest, db: AsyncSession = Depends(get_db)):
    """
    保存当前图谱到数据库
    传 {"topic": "...", "graph": {...}} → 返回保存的 id
    """
    try:
        graph_id = await graph_dal.save(db, topic=req.topic, graph=req.graph)
        return {"success": True, "id": graph_id, "message": "图谱已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败：{str(e)}")


# ---- 覆盖更新请求模型 ----
class GraphUpdateRequest(BaseModel):
    graph: KnowledgeGraph


@router.put("/update/{graph_id}")
async def update_graph(graph_id: int, req: GraphUpdateRequest, db: AsyncSession = Depends(get_db)):
    """
    覆盖更新指定图谱（自动保存同步用）
    传 {"graph": {...}} → 节点和边全量替换
    """
    try:
        ok = await graph_dal.update(db, graph_id=graph_id, graph=req.graph)
        if not ok:
            raise HTTPException(status_code=404, detail="图谱不存在")
        return {"success": True, "id": graph_id, "message": "图谱已更新"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新失败：{str(e)}")


@router.get("/list")
async def list_graphs(db: AsyncSession = Depends(get_db)):
    """
    列出所有已保存的图谱（最近 20 条）
    """
    try:
        items = await graph_dal.list_all(db)
        return {"success": True, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取列表失败：{str(e)}")


@router.get("/load/{graph_id}", response_model=GraphResponse)
async def load_graph(graph_id: int, db: AsyncSession = Depends(get_db)):
    """
    按 id 加载完整图谱
    """
    try:
        graph = await graph_dal.load(db, graph_id)
        if not graph:
            return GraphResponse(success=False, message="图谱不存在")

        return GraphResponse(
            success=True,
            graph=graph,
            message=f"已加载「图谱 #{graph_id}」",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"加载失败：{str(e)}")


@router.delete("/delete/{graph_id}")
async def delete_graph(graph_id: int, db: AsyncSession = Depends(get_db)):
    """
    删除指定图谱
    """
    try:
        ok = await graph_dal.delete(db, graph_id)
        if not ok:
            raise HTTPException(status_code=404, detail="图谱不存在")
        return {"success": True, "message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败：{str(e)}")
