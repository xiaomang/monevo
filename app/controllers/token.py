"""令牌接口:支持账号密码登录与刷新令牌两种发牌方式。"""

import time
from typing import Annotated

import jwt
from anyio import to_thread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from bson import ObjectId
from bson.errors import InvalidId
from litestar import Controller, post
from litestar.di import NamedDependency
from litestar.exceptions import HTTPException
from litestar.params import JSONBody
from msgspec import Meta, Struct
from pymongo.asynchronous.database import AsyncDatabase

from app.settings import Settings


class TokenCreateByPasswordInput(Struct, tag_field="grant_type", tag="password"):
    """账号密码模式入参,请求体需带 "grant_type": "password"。"""

    username: Annotated[str, Meta(description="用户名", min_length=2, max_length=20)]
    password: Annotated[str, Meta(description="密码", min_length=6, max_length=20)]


class TokenCreateByRefreshInput(Struct, tag_field="grant_type", tag="refresh"):
    """刷新令牌模式入参,请求体需带 "grant_type": "refresh"。"""

    refresh_token: Annotated[str, Meta(description="刷新令牌")]


class TokenCreateOutput(Struct):
    """令牌响应体。"""

    access_token: Annotated[str, Meta(description="访问令牌")]
    refresh_token: Annotated[str, Meta(description="刷新令牌")]
    token_type: Annotated[str, Meta(description="令牌类型")] = "Bearer"


class TokenController(Controller):
    """令牌控制器。"""

    path = "/tokens"
    tags = ["令牌"]

    @post(summary="创建令牌")
    async def create(
        self,
        data: JSONBody[TokenCreateByPasswordInput | TokenCreateByRefreshInput],
        db: NamedDependency[AsyncDatabase],
        settings: NamedDependency[Settings],
    ) -> TokenCreateOutput:
        """签发访问令牌与刷新令牌,按 grant_type 区分两种入参。"""
        iat = int(time.time())
        if isinstance(data, TokenCreateByPasswordInput):
            # 密码模式:校验用户名密码
            user = await db.users.find_one({"username": data.username})
            if not user:
                raise HTTPException(status_code=400, detail="用户名密码错误")
            hasher = PasswordHasher()
            # argon2 校验是 CPU 密集的同步调用,放到线程池执行以免阻塞事件循环;
            # 密码不匹配或哈希非法时 argon2 抛异常而非返回 False,统一按登录失败处理。
            # 同时账号不存在与密码错误返回同一提示,避免用户名被探测。
            try:
                await to_thread.run_sync(hasher.verify, user["password"], data.password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                raise HTTPException(status_code=400, detail="用户名密码错误") from None
        else:
            # 刷新模式:验签并解出刷新令牌,再确认用户仍然存在
            try:
                payload = jwt.decode(
                    jwt=data.refresh_token,
                    key=settings.jwt_refresh_key,
                    algorithms=[settings.jwt_algorithm],
                )
                # 沿用原签发时间,使刷新令牌不会随刷新无限续期
                iat = int(payload["iat"])
                user_id = ObjectId(payload["sub"])
            except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, InvalidId):
                # 过期、签名错误、缺少 claim 或 ID 非法,一律视为无效刷新令牌
                raise HTTPException(status_code=400, detail="刷新令牌错误") from None
            user = await db.users.find_one({"_id": user_id})
            if not user:
                raise HTTPException(status_code=400, detail="刷新令牌错误")
        user_id = str(user["_id"])
        # 访问令牌只带 sub / usr / exp,供后续鉴权解析
        access_token = jwt.encode(
            payload={
                "sub": user_id,
                "usr": user["username"],
                "iat": iat,
                "exp": iat + settings.jwt_access_expires,
            },
            key=settings.jwt_access_key,
            algorithm=settings.jwt_algorithm,
        )
        # 刷新令牌只带 sub / iat / exp,不包含用户名等信息
        refresh_token = jwt.encode(
            payload={
                "sub": user_id,
                "iat": iat,
                "exp": iat + settings.jwt_refresh_expires,
            },
            key=settings.jwt_refresh_key,
            algorithm=settings.jwt_algorithm,
        )
        return TokenCreateOutput(
            access_token=access_token,
            refresh_token=refresh_token,
        )
