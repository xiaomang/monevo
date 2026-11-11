"""依赖注入函数:从应用 state 中取出 lifespan 阶段创建的对象。"""

from litestar.datastructures import State
from pymongo.asynchronous.database import AsyncDatabase

from app.settings import Settings


async def mongo_dependency(state: State) -> AsyncDatabase:
    """提供 MongoDB 数据库句柄,连接池由 lifespan 统一创建与关闭。"""
    return state["db"]


async def settings_dependency(state: State) -> Settings:
    """提供应用配置对象。"""
    return state["settings"]
