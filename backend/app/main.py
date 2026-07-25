"""
HyGraph - AI 知识图谱助手
FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.routers import graph, chat
from app.db.database import init_db


# ============================================================
# 应用生命周期（启动时自动建表）
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库，关闭时清理资源"""
    print("[HyGraph] 正在初始化数据库...")
    await init_db()
    print("[HyGraph] 数据库初始化完成")
    yield  # 这里是应用运行期间
    print("[HyGraph] 应用已关闭")


# ============================================================
# 创建 FastAPI 应用实例
# ============================================================
app = FastAPI(
    title="HyGraph",
    description="AI 知识图谱生成助手 - 基于腾讯混元 Hy3 API",
    version="0.1.0",
    lifespan=lifespan,
)

# ============================================================
# CORS 中间件（允许前端跨域访问后端 API）
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 健康检查接口
# ============================================================
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "HyGraph 后端运行正常"}


# ============================================================
# 注册业务路由
# ============================================================
app.include_router(graph.router)
app.include_router(chat.router)


# ============================================================
# 挂载静态文件（必须放在路由注册的最后面）
# ============================================================
static_dir = Path(__file__).parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
