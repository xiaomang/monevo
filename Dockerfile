# 与本地虚拟环境保持一致的 Python 版本
FROM python:3.14-slim

# 不生成 .pyc、日志不缓冲(容器日志可实时输出)、pip 不缓存
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先安装依赖,利用镜像层缓存:只有 requirements.txt 变化时才重新安装
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 以非 root 用户运行,降低容器内进程权限
RUN useradd --create-home --uid 10001 appuser

COPY --chown=appuser:appuser app ./app

USER appuser

EXPOSE 8000

# 配置全部来自环境变量(变量清单见 .env.example),不要把 .env 打进镜像;
# 运行时通过 docker run --env-file .env 或编排平台注入。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
