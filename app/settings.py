"""应用配置:字段可由 .env 文件或同名(大写)环境变量覆盖。"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 调试模式,开启后返回详细错误信息
    debug: bool = False

    # MongoDB 连接串与数据库名
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "monevo"

    # JWT 签名算法与有效期(单位:秒)
    jwt_algorithm: str = "HS256"
    jwt_access_expires: int = 3600  # 访问令牌 1 小时
    jwt_refresh_expires: int = 86400  # 刷新令牌 24 小时

    # 签名密钥只从 .env / 环境变量读取,不提供默认值,避免用弱密钥上线。
    # 读取顺序:环境变量 > .env,变量名为字段名的大写形式
    # (例如 JWT_ACCESS_KEY -> jwt_access_key),大小写不敏感。
    # HS256 使用 256 位密钥,因此长度至少 32 字节,不足会在启动时报校验错误。
    #
    # 密钥轮换说明:
    # - 仅支持单密钥,没有 key id / 密钥环,换密钥后旧密钥签发的令牌立即失效;
    # - 轮换需修改 .env(或环境变量)并重启服务,配置在导入时加载;
    # - 建议先轮换 jwt_access_key:访问令牌失效后,客户端可用仍有效的刷新令牌
    #   换发新访问令牌,无需重新登录;等 jwt_access_expires 过后再轮换
    #   jwt_refresh_key(会导致所有用户重新登录);
    # - 两个密钥都必须是随机值,且不同环境(开发/测试/生产)各用一套,不可复用。
    jwt_access_key: str = Field(min_length=32, description="访问令牌签名密钥")
    jwt_refresh_key: str = Field(min_length=32, description="刷新令牌签名密钥")

    # 启动时自动创建的默认调试账号,便于本地登录测试。
    # 仅用于开发/测试环境,生产部署应改为强口令或移除该启动钩子。
    default_username: str = "冲锋号"
    default_password: str = "123456"

    # 从项目根目录的 .env 读取配置;环境变量同名时优先生效
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
