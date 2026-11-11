# monevo

基于 Litestar + MongoDB 的接口服务。

## Docker 部署

以下命令在项目根目录执行，需要 Docker 20.10+（Windows / macOS 用 Docker Desktop）。

### 1. 准备配置

```bash
cp .env.example .env
```

编辑 `.env`，至少确认以下几项：

| 变量 | 说明 |
| --- | --- |
| `MONGO_URI` | 容器内访问 Mongo 时填 `mongodb://monevo-mongo:27017`（用容器名当主机名） |
| `JWT_ACCESS_KEY` / `JWT_REFRESH_KEY` | 必填，长度至少 32 字节，否则启动直接报错 |
| `DEFAULT_PASSWORD` | 默认调试账号密码，生产务必改掉 |
| `DEBUG` | 生产设为 `False` |

生成密钥：

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`.env` 不会被打进镜像（已在 `.dockerignore` 中排除），运行时通过 `--env-file` 注入。

### 2. 构建镜像

```bash
docker build -t monevo:latest .
```

### 3. 部署 MongoDB

```bash
docker network create monevo-net

docker run -d \
  --name monevo-mongo \
  --network monevo-net \
  -v monevo-mongo-data:/data/db \
  -p 27017:27017 \
  mongo:7
```

- `-v monevo-mongo-data:/data/db`：数据持久化到命名卷，删除容器不丢数据；宿主机需要直连调试时才暴露 `27017`。
- 上面的启动方式**未开启鉴权**，仅适合本机/内网。生产环境应启用认证：

  ```bash
  docker run -d \
    --name monevo-mongo \
    --network monevo-net \
    -v monevo-mongo-data:/data/db \
    -e MONGO_INITDB_ROOT_USERNAME=monevo \
    -e MONGO_INITDB_ROOT_PASSWORD=<强口令> \
    mongo:7
  ```

  此时 `.env` 中的 `MONGO_URI` 改为：

  ```
  MONGO_URI = mongodb://monevo:<强口令>@monevo-mongo:27017/?authSource=admin
  ```

### 4. 启动应用

```bash
docker run -d \
  --name monevo-api \
  --network monevo-net \
  --env-file .env \
  -p 8000:8000 \
  monevo:latest
```

应用与 Mongo 必须在同一网络（`--network monevo-net`），否则容器名 `monevo-mongo` 无法解析。

启动时会自动创建 `DEFAULT_USERNAME` / `DEFAULT_PASSWORD` 对应的调试账号（已存在则跳过）。

### 5. 验证

```bash
# 容器状态
docker ps

# 文档页（不依赖 Mongo）
curl -I http://localhost:8000/schema

# OpenAPI JSON
curl http://localhost:8000/schema/openapi.json

# 业务接口（需要 Mongo 可连通）
curl http://localhost:8000/
```

浏览器打开 `http://localhost:8000/schema/` 可查看接口文档。

### 6. 使用 Docker Compose（可选）

把以下内容保存为 `docker-compose.yml`：

```yaml
services:
  mongo:
    image: mongo:7
    restart: unless-stopped
    volumes:
      - mongo-data:/data/db
    # 生产环境取消注释并设置口令
    # environment:
    #   MONGO_INITDB_ROOT_USERNAME: monevo
    #   MONGO_INITDB_ROOT_PASSWORD: <强口令>

  api:
    build: .
    restart: unless-stopped
    env_file: .env
    environment:
      MONGO_URI: mongodb://mongo:27017
    ports:
      - "8000:8000"
    depends_on:
      - mongo

volumes:
  mongo-data:
```

然后：

```bash
docker compose up -d --build   # 构建并启动
docker compose logs -f api     # 查看日志
docker compose down            # 停止并删除容器(数据卷保留)
```

注意 Compose 里服务名是 `mongo`，所以 `MONGO_URI` 要覆盖为 `mongodb://mongo:27017`。

### 7. 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| 启动日志报 `Field required`，容器退出 | `.env` 缺少 `JWT_ACCESS_KEY` / `JWT_REFRESH_KEY` |
| 报 `String should have at least 32 characters` | 密钥长度不足，重新生成 |
| 接口 500，日志显示连接超时 / `ServerSelectionTimeoutError` | 两个容器不在同一网络，或 `MONGO_URI` 主机名写错 |
| `bind: address already in use` | 宿主机 8000/27017 被占用，改 `-p 8001:8000` 这类映射 |
| 修改 `.env` 后配置未生效 | 环境变量在容器启动时读取，需 `docker restart monevo-api`（身份/密钥变更则重建容器） |
| 改了代码但接口没变 | 镜像内是构建时的代码，重新 `docker build` 并重建容器 |

查看日志：

```bash
docker logs -f monevo-api
```

### 8. 更新部署

```bash
docker build -t monevo:latest .
docker rm -f monevo-api
docker run -d --name monevo-api --network monevo-net --env-file .env -p 8000:8000 monevo:latest
```

轮换 `JWT_ACCESS_KEY` / `JWT_REFRESH_KEY` 后，已签发的令牌会立即失效；建议先轮换访问密钥，等访问令牌过期后再轮换刷新密钥，避免所有用户同时被强制重新登录。

## 本地开发

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
litestar --app app.main:app run --reload
```

默认监听 `http://127.0.0.1:8000`，文档页为 `/schema/`。
