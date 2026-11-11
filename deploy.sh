#!/usr/bin/env bash
# monevo Ubuntu 部署脚本(基于 Docker)
#
# 用法:
#   ./deploy.sh
#
# 可选覆盖(环境变量):
#   IMAGE=monevo TAG=latest APP_PORT=8000 ./deploy.sh
#   MONGO_IMAGE=mongo:7 MONGO_VOLUME=monevo-mongo-data ./deploy.sh
#
# 首次部署前请先准备配置: cp .env.example .env && 编辑 .env
set -euo pipefail

IMAGE="${IMAGE:-monevo}"
TAG="${TAG:-latest}"
APP_PORT="${APP_PORT:-8000}"
NETWORK="${NETWORK:-monevo-net}"
MONGO_CONTAINER="${MONGO_CONTAINER:-monevo-mongo}"
API_CONTAINER="${API_CONTAINER:-monevo-api}"
MONGO_IMAGE="${MONGO_IMAGE:-mongo:7}"
MONGO_VOLUME="${MONGO_VOLUME:-monevo-mongo-data}"
ENV_FILE="${ENV_FILE:-.env}"

log() { printf '\033[32m[deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[deploy]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[deploy]\033[0m %s\n' "$*" >&2; exit 1; }

# 读取 .env 中某个键的值(忽略注释和空行)
env_value() {
    local key="$1" line
    line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE" | tail -n 1 || true)"
    if [ -z "$line" ]; then
        return 0
    fi
    printf '%s' "${line#*=}" | tr -d '[:space:]'
}

check_docker() {
    command -v docker >/dev/null 2>&1 || die "未找到 docker,请先安装: https://docs.docker.com/engine/install/ubuntu/"
    if ! docker info >/dev/null 2>&1; then
        die "无法访问 Docker 守护进程,请使用 sudo 执行,或把当前用户加入 docker 组: sudo usermod -aG docker \$USER && newgrp docker"
    fi
}

check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f .env.example ]; then
            cp .env.example "$ENV_FILE"
            die "已从 .env.example 生成 $ENV_FILE,请先填写密钥后重新执行"
        fi
        die "缺少 $ENV_FILE,请参考 .env.example 创建"
    fi

    local key value
    for key in JWT_ACCESS_KEY JWT_REFRESH_KEY; do
        value="$(env_value "$key")"
        [ -n "$value" ] || die "$ENV_FILE 中缺少 $key"
        case "$value" in
            replace-*) die "$ENV_FILE 中 $key 仍是示例值,请替换为随机密钥" ;;
        esac
        [ "${#value}" -ge 32 ] || die "$ENV_FILE 中 $key 长度不足 32 字节"
    done

    if [ "$(env_value DEBUG)" = "True" ] || [ "$(env_value DEBUG)" = "true" ]; then
        warn "DEBUG 当前为 True,生产环境建议设为 False"
    fi
}

ensure_network() {
    if docker network inspect "$NETWORK" >/dev/null 2>&1; then
        log "网络 $NETWORK 已存在"
    else
        docker network create "$NETWORK" >/dev/null
        log "已创建网络 $NETWORK"
    fi
}

ensure_mongo() {
    if docker ps -a --format '{{.Names}}' | grep -qx "$MONGO_CONTAINER"; then
        if [ "$(docker inspect -f '{{.State.Running}}' "$MONGO_CONTAINER")" = "true" ]; then
            log "MongoDB 容器 $MONGO_CONTAINER 已在运行"
        else
            docker start "$MONGO_CONTAINER" >/dev/null
            log "已启动已有 MongoDB 容器 $MONGO_CONTAINER"
        fi
        return
    fi

    # 不向宿主机暴露 27017,仅容器网络内可访问;需要本机调试时自行加 -p 27017:27017
    docker run -d \
        --name "$MONGO_CONTAINER" \
        --network "$NETWORK" \
        --restart unless-stopped \
        -v "$MONGO_VOLUME":/data/db \
        "$MONGO_IMAGE" >/dev/null
    log "已创建 MongoDB 容器 $MONGO_CONTAINER(数据卷 $MONGO_VOLUME)"
}

wait_for_mongo() {
    local i
    for i in $(seq 1 30); do
        if docker exec "$MONGO_CONTAINER" mongosh --quiet --eval 'db.runCommand({ ping: 1 }).ok' 2>/dev/null | grep -q 1; then
            log "MongoDB 就绪"
            return
        fi
        sleep 1
    done
    warn "MongoDB 30 秒内未就绪,继续部署,请稍后检查: docker logs $MONGO_CONTAINER"
}

deploy_app() {
    log "构建镜像 $IMAGE:$TAG"
    docker build -t "$IMAGE:$TAG" .

    if docker ps -a --format '{{.Names}}' | grep -qx "$API_CONTAINER"; then
        docker rm -f "$API_CONTAINER" >/dev/null
        log "已移除旧的应用容器 $API_CONTAINER"
    fi

    docker run -d \
        --name "$API_CONTAINER" \
        --network "$NETWORK" \
        --restart unless-stopped \
        --env-file "$ENV_FILE" \
        -p "$APP_PORT":8000 \
        "$IMAGE:$TAG" >/dev/null
    log "已启动应用容器 $API_CONTAINER,映射端口 $APP_PORT -> 8000"
}

health_check() {
    local i url="http://127.0.0.1:${APP_PORT}/schema/openapi.json"
    for i in $(seq 1 30); do
        if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
            log "健康检查通过: $url"
            return
        fi
        if [ "$(docker inspect -f '{{.State.Running}}' "$API_CONTAINER" 2>/dev/null)" != "true" ]; then
            docker logs --tail 50 "$API_CONTAINER" || true
            die "应用容器已退出,请检查上面的日志"
        fi
        sleep 1
    done
    docker logs --tail 50 "$API_CONTAINER" || true
    die "健康检查超时(30 秒),请检查日志"
}

main() {
    check_docker
    check_env_file
    ensure_network
    ensure_mongo
    wait_for_mongo
    deploy_app
    health_check

    log "部署完成"
    echo "  文档: http://<服务器地址>:${APP_PORT}/schema/"
    echo "  日志: docker logs -f ${API_CONTAINER}"
    echo "  配置变更后需重启: docker restart ${API_CONTAINER}"
}

main "$@"
