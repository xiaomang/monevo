"""首页 / 健康检查接口。"""

from typing import Annotated

from litestar import Controller, get
from msgspec import Meta, Struct


class HomeFindOutput(Struct):
    """健康检查响应体。"""

    status: Annotated[str, Meta(description="状态")]


class HomeController(Controller):
    """首页控制器,当前仅提供健康检查。"""

    path = "/"

    @get(summary="健康检查")
    async def find(self) -> HomeFindOutput:
        """返回固定的成功状态,用于探活。"""
        return HomeFindOutput(status="Success")
