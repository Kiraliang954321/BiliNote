# GHCR Docker Release Design

> Date: 2026-09-17
> Repository: `G:\Project\bilinote\source`
> GitHub: `Kiraliang954321/BiliNote`

## Goal

让其他用户只需要 Docker，就能从公开 GHCR 镜像部署当前 BiliNote fork；同时保留现有开发者本地构建流程，不把发布部署与开发 Compose 混在一起。

## Current State

- `Dockerfile.complete` 已能构建完整单镜像：backend + frontend + nginx + ffmpeg。
- `.github/workflows/docker-build.yml` 已存在，并使用 `Dockerfile.complete` 与 `ghcr.io/kiraliang954321/bilinote`。
- Docker workflow 监听 `master`、`docker-v*` tag 和手动触发；Docker 专用 tag 避免与同样监听 `v*` 的 desktop/extension release workflow 耦合。
- 发布使用两个原生 GitHub-hosted runner：`ubuntu-24.04` 构建 `linux/amd64`，`ubuntu-24.04-arm` 构建 `linux/arm64`；不使用 QEMU。
- 当前 `docker-compose.yml` 是开发栈：backend/frontend/nginx 分离、本地 build、backend bind mount。它不应被替换成最终用户发布配置。
- README 中 Docker 快速开始已使用本 fork 的发布 Compose/GHCR 镜像 `ghcr.io/kiraliang954321/bilinote:latest`。

## Approaches Considered

### A. Replace the existing `docker-compose.yml` with a release Compose

优点：clone 后可直接 `docker compose up -d`。

缺点：会破坏现有开发三容器构建/调试流程，并改变上游已有开发约定。拒绝。

### B. Add an installer script that downloads Compose and starts Docker

优点：最终用户命令最短。

缺点：额外增加 PowerShell/Bash 两套安装逻辑、网络下载与脚本安全问题；当前发布链路本身还没验证，不应先增加第二层安装器。首版不做。

### C. Keep the development Compose and add a release Compose

采用此方案。

- 保留 `docker-compose.yml`，继续服务源码开发。
- 新增 `docker-compose.release.yml`，只使用公开预构建镜像。
- 用户 clone 后执行一条 Compose 命令即可启动。
- 后续如确实需要，可在这个稳定入口之上再增加安装脚本。

## Release Image

公开镜像固定为：

```text
ghcr.io/kiraliang954321/bilinote
```

发布平台：

```text
linux/amd64
linux/arm64
```

用途：Windows Docker Desktop、Linux x86_64，以及 ARM64 Docker 主机。

首次成功推送 GHCR package 后，package visibility 必须设置为 **Public**，否则未登录用户无法直接 pull。

## Workflow Design

复用并修改现有 `.github/workflows/docker-build.yml`，不创建第二套 Docker publish workflow。

触发规则：

```text
push master      -> latest + sha-* tags
workflow_dispatch -> latest + sha-* tags
docker-v* tag    -> latest + version + sha-* tags
```

Docker 版本 tag 使用独立命名空间，例如：

```text
docker-v1.0.0
```

而不是 `v1.0.0`。原因是现有 desktop 与 extension workflows 均监听 `v*`；Docker 专用 tag 可避免仅发布 Docker 时意外触发桌面包和扩展发布。

GitHub Actions 构建顺序：

```text
matrix: ubuntu-24.04 builds linux/amd64; ubuntu-24.04-arm builds linux/arm64 (parallel)
-> each runner: checkout -> setup Buildx -> login GHCR with GITHUB_TOKEN
-> each runner: build Dockerfile.complete and push a canonical digest
-> upload each digest artifact
-> merge job: download digests -> docker metadata -> imagetools create final tags
-> imagetools inspect the published manifest
```

每个平台使用独立的 GHA cache scope，避免跨架构缓存碰撞。最终 merge job 只把两个 digest 合成为 `latest`、版本和 `sha-*` 标签，因此公开 manifest 仅包含 `linux/amd64` 与 `linux/arm64`。

权限保持最小化：

```yaml
contents: read
packages: write
```

不新增 PAT secret；使用仓库提供的 `GITHUB_TOKEN`。

## Tag Semantics

- `latest`: 当前稳定公开版本；master push、手动发布和 `docker-v*` 发布都会更新。
- `1.0.0`: 来自 `docker-v1.0.0`，用于固定版本部署。
- `1.0`: 同一个 semver release 的 major.minor 标签。
- `sha-<shortsha>`: 每次构建的不可变 Git 对应标签，用于精确回滚与验收。

merge job 从 `docker-v*` ref name 去除 `docker-v` 前缀后，将结果作为 `docker/metadata-action` 的 semver `value`。两条 semver 规则都只在该 value 非空时启用；因此 `docker-v1.2.3` 生成 `1.2.3` 和 `1.2`，但不生成 major-only `1`。master 和手动触发传入空值，不生成 semver 标签。metadata 配置 `flavor.latest=false`，所以 `latest` 只由显式的 `type=raw,value=latest` 规则生成；所有触发方式均生成 `latest` 和 `sha-*`。

`Dockerfile.complete` 的 `VITE_APP_VERSION`：

- `docker-v1.2.3` 时注入 `1.2.3`。
- master / manual build 未指定版本时保持现有 fallback 行为。

## Release Compose

新增 `docker-compose.release.yml`：

```yaml
services:
  bilinote:
    image: ghcr.io/kiraliang954321/bilinote:${BILINOTE_TAG:-latest}
    container_name: bilinote
    ports:
      - "${APP_PORT:-3015}:80"
    volumes:
      - bilinote-data:/app/backend/data
      - bilinote-config:/app/backend/config
      - bilinote-static:/app/backend/static
      - bilinote-models:/app/backend/models
    restart: unless-stopped

volumes:
  bilinote-data:
  bilinote-config:
  bilinote-static:
  bilinote-models:
```

默认不要求 `.env`。用户可选覆盖：

```text
APP_PORT=3016
BILINOTE_TAG=1.0.0
```

四个命名卷只挂数据子目录，不挂整个 `/app/backend`，确保镜像升级时不会被旧代码覆盖。

## User Flow

首次部署：

```bash
git clone https://github.com/Kiraliang954321/BiliNote.git
cd BiliNote
docker compose -f docker-compose.release.yml up -d
```

访问：

```text
http://localhost:3015
```

更新 latest：

```bash
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

固定版本：

```bash
BILINOTE_TAG=1.0.0 docker compose -f docker-compose.release.yml up -d
```

Windows PowerShell 对应使用：

```powershell
$env:BILINOTE_TAG="1.0.0"
docker compose -f docker-compose.release.yml up -d
Remove-Item Env:BILINOTE_TAG
```

## Documentation Changes

README 的 Docker 快速开始应优先展示本 fork 的 release Compose 和：

```text
ghcr.io/kiraliang954321/bilinote:latest
```

保留“源码本地 build”作为开发/高级用法，并明确：

- `docker-compose.release.yml` = 最终用户预构建镜像部署。
- `docker-compose.yml` = 开发者源码构建。
- 当前 fork 的默认访问端口为 3015。
- `docker compose down` 不删除命名卷；`docker compose down -v` 会删除数据。
- GHCR 第一次发布后需要将 package 设置为 Public。

## Validation

实现后必须验证：

1. GitHub Actions workflow YAML 可解析，触发规则不再与 `v*` desktop/extension tag 冲突。
2. `docker compose -f docker-compose.release.yml config` 成功，且解析出的 image 为 `ghcr.io/kiraliang954321/bilinote:latest`、端口为 `3015:80`、四个 volume 均存在。
3. 本地 `docker-compose.yml` 内容不被改成 release 配置。
4. README 不再把本 fork 的推荐 Docker 命令指向 `ghcr.io/jefferyhcool/bilinote:latest`。
5. push 到 `master` 后 GitHub Actions 成功构建并推送 GHCR manifest。
6. 从未登录 Docker 客户端执行 `docker pull ghcr.io/kiraliang954321/bilinote:latest` 成功；如果失败，则完成 GHCR Public visibility 后再次验证。
7. 使用 release Compose 启动后 HTTP 返回 200，持久化卷在容器重建后仍存在。

## Non-Goals

首版不做：

- `install.ps1` / `install.sh` 一键安装器。
- Kubernetes / Helm。
- Docker Hub 同步发布。
- 自动删除旧 GHCR image versions。
- 修改现有开发 `docker-compose.yml` 的架构。
- 改动 BiliNote 应用业务逻辑。
