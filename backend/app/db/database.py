"""
数据库连接模块
管理 SQLAlchemy 异步引擎和会话
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


# ============================================================
# 创建异步引擎 → 连接 MySQL
# ============================================================
# echo=True 会打印所有 SQL 语句（调试用，生产环境关掉）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=5,        # 连接池大小
    pool_recycle=3600,  # 连接回收时间（秒）
)

# ============================================================
# 会话工厂
# ============================================================
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 提交后不把对象标记为过期
)


# ============================================================
# 模型基类（所有 ORM 模型继承这个）
# ============================================================
class Base(DeclarativeBase):
    pass


# ============================================================
# FastAPI 依赖注入：在请求中自动获取和关闭数据库会话
# ============================================================
async def get_db() -> AsyncSession:
    """每个 API 请求进来时创建会话，结束时关闭"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ============================================================
# 初始化数据库（自动建库 + 建表）
# ============================================================
async def _create_database_if_not_exists():
    """先连 MySQL（不指定库名），如果 hygraph 库不存在就创建它"""
    import aiomysql

    conn = await aiomysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
    )
    async with conn.cursor() as cur:
        await cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{settings.DB_NAME}` "
            "DEFAULT CHARACTER SET utf8mb4"
        )
        await conn.commit()
    conn.close()


async def init_db():
    """应用启动时调用：自动建库（如果没有）+ 自动创建所有表"""
    await _create_database_if_not_exists()
    async with engine.begin() as conn:
        # 导入所有模型，确保 Base.metadata 包含它们
        from app.db.models import GraphRecord, NodeRecord, EdgeRecord, MessageRecord  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)
