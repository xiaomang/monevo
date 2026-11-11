"""应用入口:装配 Litestar 应用,注册路由、依赖、生命周期钩子与 OpenAPI 文档。"""

import logging

from bson import ObjectId
from litestar import Litestar
from litestar.datastructures import State
from litestar.di import Provide
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import RedocRenderPlugin

from app.controllers.home import HomeController
from app.controllers.token import TokenController
from app.dependencies import mongo_dependency, settings_dependency
from app.hooks import set_default_user_on_startup
from app.lifespan import mongo_lifespan
from app.settings import Settings

logger = logging.getLogger(__name__)

# 应用级配置,字段可由 .env / 环境变量覆盖
settings = Settings()

app = Litestar(
    debug=settings.debug,
    # 配置放入应用 state,供 lifespan 与依赖注入读取
    state=State({"settings": settings}),
    # 启动时建立 MongoDB 连接,关闭时释放
    lifespan=[mongo_lifespan],
    # 启动后确保默认调试账号存在
    on_startup=[set_default_user_on_startup],
    dependencies={
        # 路由参数声明 db / settings 即可自动注入
        "db": Provide(mongo_dependency),
        "settings": Provide(settings_dependency),
    },
    route_handlers=[HomeController, TokenController],
    # msgspec 无法直接序列化 ObjectId,统一编码为字符串
    type_encoders={ObjectId: str},
    openapi_config=OpenAPIConfig(
        title="Monevo API",
        version="1.0.0",
        render_plugins=[
            # 必须固定 Redoc 版本:3.x 的 standalone bundle 使用 import.meta,
            # 需以 <script type="module"> 加载,而 Litestar 模板生成的是普通 script,
            # 会报 "Redoc is not defined"。v2.5.0 是最后一个 UMD 版本。
            RedocRenderPlugin(version="v2.5.0")
        ],
    ),
)
