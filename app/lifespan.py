import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from litestar import Litestar
from pymongo import AsyncMongoClient

logger = logging.getLogger(__name__)


@asynccontextmanager
async def mongo_lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    """MongoDB 生命周期管理器:启动时建立连接并放入 state,关闭时释放。"""
    settings = app.state["settings"]
    # 复用同一个客户端,所有请求共享其连接池
    client = AsyncMongoClient[Any](settings.mongo_uri)
    logger.info("Connected to MongoDB")
    app.state["db"] = client[settings.mongo_database]
    yield
    # yield 之后的逻辑在应用关闭时执行
    await client.close()
    logger.info("Disconnected from MongoDB")
