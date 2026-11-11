"""应用启动钩子。"""

import logging
import time

from anyio import to_thread
from argon2 import PasswordHasher
from litestar import Litestar
from pymongo.asynchronous.database import AsyncDatabase

from app.settings import Settings

logger = logging.getLogger(__name__)


async def set_default_user_on_startup(app: Litestar) -> None:
    """确保存在默认调试账号,便于本地直接登录测试。"""
    db: AsyncDatabase = app.state["db"]
    settings: Settings = app.state["settings"]
    username = settings.default_username
    password = settings.default_password
    # 已存在则跳过,避免重复写入
    if await db.users.count_documents({"username": username}) > 0:
        return
    # 库中只存 argon2 哈希,不保存明文密码
    hasher = PasswordHasher()
    # 哈希是 CPU 密集的同步调用,放到线程池执行,避免阻塞启动期间的事件循环
    hashed_password = await to_thread.run_sync(hasher.hash, password)
    doc = {
        "username": username,
        "password": hashed_password,
        "created": time.time(),
        "ip": "localhost",
    }
    await db.users.insert_one(doc)
