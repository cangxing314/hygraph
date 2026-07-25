"""
全局配置模块
把所有环境变量和配置项集中管理，其他模块只引用这里
"""

import os
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()


class Settings:
    """应用配置"""

    # ========== 应用基础配置 ==========
    APP_NAME: str = "HyGraph - AI 知识图谱助手"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # ========== Hy3 API 配置 ==========
    HY3_API_KEY: str = os.getenv("HY3_API_KEY", "")
    HY3_BASE_URL: str = os.getenv("HY3_BASE_URL", "https://tokenhub.tencentmaas.com/v1")
    HY3_MODEL: str = os.getenv("HY3_MODEL", "hy3")
    # API 调用超时时间（秒）
    HY3_TIMEOUT: int = int(os.getenv("HY3_TIMEOUT", "30"))

    # ========== 数据库配置 ==========
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: int = int(os.getenv("DB_PORT", "3306"))
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "hygraph")

    @property
    def DATABASE_URL(self) -> str:
        """拼接完整数据库连接地址（异步驱动）"""
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


# 全局单例，其他地方 `from app.core.config import settings` 即可
settings = Settings()
