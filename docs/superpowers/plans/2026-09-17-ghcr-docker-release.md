# GHCR Docker Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish this BiliNote fork as a public multi-architecture GHCR image and provide a release Compose path that lets users deploy it with Docker without building source locally.

**Architecture:** Reuse the existing `.github/workflows/docker-build.yml` and `Dockerfile.complete`. Keep the existing development `docker-compose.yml` unchanged, add a separate `docker-compose.release.yml` that consumes `ghcr.io/kiraliang954321/bilinote`, and update README deployment instructions to point users at the fork image and release Compose. Docker releases use `docker-v*` tags to avoid triggering existing desktop/extension `v*` workflows.

**Tech Stack:** GitHub Actions, Docker Buildx, QEMU, GHCR, Docker Compose, Markdown.

**Spec:** `docs/superpowers/specs/2026-09-17-ghcr-docker-release-design.md`

## Global Constraints

- Public image name is exactly `ghcr.io/kiraliang954321/bilinote`.
- Preserve the existing development `docker-compose.yml`; do not replace it with release deployment configuration.
- Reuse `.github/workflows/docker-build.yml`; do not create a second parallel Docker publish workflow.
- Docker release tags use `docker-v*`, not `v*`, because desktop and extension workflows already listen to `v*`.
- Published platforms are `linux/amd64` and `linux/arm64`.
- Use repository `GITHUB_TOKEN`; do not introduce a PAT secret.
- Release Compose defaults to host port `3015` and four persistent Docker volumes for `/app/backend/data`, `/app/backend/config`, `/app/backend/static`, and `/app/backend/models`.
- Do not add installer scripts, Kubernetes/Helm, Docker Hub publishing, or application business-logic changes.

---

### Task 1: Make the existing Docker workflow publish the fork image safely

**Files:**
- Modify: `.github/workflows/docker-build.yml`
- Test: workflow syntax/trigger inspection and local textual assertions

**Interfaces:**
- Consumes: `Dockerfile.complete`, GitHub repository owner/name, `GITHUB_TOKEN`.
- Produces: GHCR tags under `ghcr.io/kiraliang954321/bilinote` for `latest`, version, and SHA; multi-arch manifest for amd64/arm64.

- [ ] **Step 1: Capture the current workflow baseline**

Run:

```powershell
Get-Content .github\workflows\docker-build.yml
Get-Content .github\workflows\main.yml -TotalCount 15
Get-Content .github\workflows\release-extension.yml -TotalCount 15
```

Expected: Docker currently listens to `v*`; desktop and extension also listen to `v*`.

- [ ] **Step 2: Modify the workflow trigger and image metadata**

Make these exact behavioral changes in `.github/workflows/docker-build.yml`:

```yaml
on:
  push:
    branches:
      - master
    tags:
      - 'docker-v*'
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: kiraliang954321/bilinote
```

Add QEMU before Buildx:

```yaml
- name: Set up QEMU
  uses: docker/setup-qemu-action@v3
```

Configure metadata so builds produce:

```yaml
tags: |
  type=raw,value=latest
  type=match,pattern=docker-v(.*),group=1
  type=sha,prefix=sha-
```

Keep:

```yaml
platforms: linux/amd64,linux/arm64
```

Update version resolution to strip `docker-v`:

```bash
if [[ "$GITHUB_REF" == refs/tags/docker-v* ]]; then
  echo "version=${GITHUB_REF_NAME#docker-v}" >> "$GITHUB_OUTPUT"
else
  echo "version=" >> "$GITHUB_OUTPUT"
fi
```

Update usage instructions to reference:

```text
ghcr.io/kiraliang954321/bilinote:latest
http://localhost:3015
```

- [ ] **Step 3: Verify no Docker workflow still listens to generic `v*`**

Run:

```powershell
Select-String -Path .github\workflows\docker-build.yml -Pattern "docker-v|branches:|master|setup-qemu|linux/amd64,linux/arm64|kiraliang954321/bilinote"
```

Expected: all listed release properties are present.

Run:

```powershell
Select-String -Path .github\workflows\docker-build.yml -Pattern "tags:\s*$|'v\*'"
```

Expected: no `'v*'` trigger in the Docker workflow.

- [ ] **Step 4: Run a YAML parse check**

Use Python if PyYAML is available:

```powershell
python -c "import yaml, pathlib; yaml.safe_load(pathlib.Path('.github/workflows/docker-build.yml').read_text(encoding='utf-8')); print('YAML_OK')"
```

If PyYAML is not installed, use Ruby or another installed YAML parser rather than changing project dependencies.

Expected: parser exits 0 and prints `YAML_OK`.

- [ ] **Step 5: Commit the workflow change**

```powershell
git add .github/workflows/docker-build.yml
git commit -m "ci(docker): publish fork image to GHCR"
```

---

### Task 2: Add the final-user release Compose

**Files:**
- Create: `docker-compose.release.yml`
- Do not modify: `docker-compose.yml`
- Test: `docker compose -f docker-compose.release.yml config`

**Interfaces:**
- Consumes: `ghcr.io/kiraliang954321/bilinote:${BILINOTE_TAG:-latest}`.
- Produces: one `bilinote` service on `${APP_PORT:-3015}:80` and four persistent named volumes.

- [ ] **Step 1: Record the development Compose checksum before editing**

Run:

```powershell
(Get-FileHash docker-compose.yml -Algorithm SHA256).Hash | Set-Content $env:TEMP\bilinote-dev-compose.sha256
```

- [ ] **Step 2: Create `docker-compose.release.yml`**

Use exactly this structure:

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

- [ ] **Step 3: Verify the release Compose default expansion**

Run:

```powershell
docker compose -f docker-compose.release.yml config
```

Expected rendered values include:

```text
image: ghcr.io/kiraliang954321/bilinote:latest
published: "3015"
target: 80
/app/backend/data
/app/backend/config
/app/backend/static
/app/backend/models
```

- [ ] **Step 4: Verify tag and port overrides**

Run:

```powershell
$env:BILINOTE_TAG="1.0.0"
$env:APP_PORT="3016"
docker compose -f docker-compose.release.yml config
Remove-Item Env:BILINOTE_TAG
Remove-Item Env:APP_PORT
```

Expected: image becomes `...:1.0.0` and published port becomes `3016`.

- [ ] **Step 5: Prove the development Compose was not changed**

Run:

```powershell
$before = Get-Content $env:TEMP\bilinote-dev-compose.sha256
$after = (Get-FileHash docker-compose.yml -Algorithm SHA256).Hash
if ($before -ne $after) { throw "development docker-compose.yml changed" }
```

Expected: exits 0.

- [ ] **Step 6: Commit the release Compose**

```powershell
git add docker-compose.release.yml
git commit -m "feat(docker): add release compose deployment"
```

---

### Task 3: Update README for the fork's one-command Docker path

**Files:**
- Modify: `README.md`
- Test: exact search assertions for image name and deployment commands

**Interfaces:**
- Consumes: workflow/tag semantics and `docker-compose.release.yml` from Tasks 1-2.
- Produces: end-user deployment/update/pinning instructions consistent with the actual release artifacts.

- [ ] **Step 1: Replace the recommended Docker quick start**

The primary fork deployment instructions must use:

```bash
git clone https://github.com/Kiraliang954321/BiliNote.git
cd BiliNote
docker compose -f docker-compose.release.yml up -d
```

Document access URL:

```text
http://localhost:3015
```

- [ ] **Step 2: Document update and version pinning**

Include:

```bash
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

And explain:

```text
BILINOTE_TAG=1.0.0
APP_PORT=3016
```

For PowerShell, show `$env:BILINOTE_TAG` / `$env:APP_PORT` syntax instead of Unix inline env syntax.

- [ ] **Step 3: Distinguish release deployment from source development**

State explicitly:

```text
docker-compose.release.yml -> final users, prebuilt GHCR image
docker-compose.yml         -> developers, local source build
```

Keep existing source-build/GPU material as advanced/development usage rather than deleting it.

- [ ] **Step 4: Document persistence and destructive volume removal**

Document the four persisted areas and explain:

```text
docker compose -f docker-compose.release.yml down
```

preserves named volumes, while:

```text
docker compose -f docker-compose.release.yml down -v
```

deletes them.

- [ ] **Step 5: Remove upstream-image recommendations from the fork's primary Docker path**

Run:

```powershell
Select-String -Path README.md -Pattern "ghcr.io/jefferyhcool/bilinote:latest"
```

Expected: no result in the fork's recommended deployment sections. Historical/changelog references are acceptable only if clearly historical, not executable deployment instructions.

Run:

```powershell
Select-String -Path README.md -Pattern "ghcr.io/kiraliang954321/bilinote|docker-compose.release.yml|localhost:3015"
```

Expected: all three are present.

- [ ] **Step 6: Commit README changes**

```powershell
git add README.md
git commit -m "docs(docker): add public GHCR deployment guide"
```

---

### Task 4: Local integration verification before pushing

**Files:**
- Verify: `.github/workflows/docker-build.yml`
- Verify: `docker-compose.release.yml`
- Verify: `README.md`
- Verify: `Dockerfile.complete`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: evidence that the repository is internally consistent before GitHub Actions is triggered.

- [ ] **Step 1: Run Compose validation again from a clean environment**

```powershell
Remove-Item Env:BILINOTE_TAG -ErrorAction SilentlyContinue
Remove-Item Env:APP_PORT -ErrorAction SilentlyContinue
docker compose -f docker-compose.release.yml config
```

Expected: image `ghcr.io/kiraliang954321/bilinote:latest`, port 3015.

- [ ] **Step 2: Build the release image locally for the current architecture**

Use a temporary verification tag and the same Dockerfile the workflow uses:

```powershell
docker build -f Dockerfile.complete -t bilinote-release-verify:local .
```

Expected: exit 0.

- [ ] **Step 3: Smoke-test the locally built image without touching the existing production container**

Run it on a temporary port/name with temporary named volumes:

```powershell
docker run -d --name bilinote-release-verify -p 3016:80 `
  -v bilinote-verify-data:/app/backend/data `
  -v bilinote-verify-config:/app/backend/config `
  -v bilinote-verify-static:/app/backend/static `
  -v bilinote-verify-models:/app/backend/models `
  bilinote-release-verify:local
```

Poll until:

```powershell
(Invoke-WebRequest http://localhost:3016 -UseBasicParsing).StatusCode
```

returns `200`.

- [ ] **Step 4: Verify persistence mounts and clean only verification resources**

Run:

```powershell
docker inspect bilinote-release-verify --format '{{range .Mounts}}{{println .Destination}}{{end}}'
docker rm -f bilinote-release-verify
docker volume rm bilinote-verify-data bilinote-verify-config bilinote-verify-static bilinote-verify-models
```

Expected mount destinations include all four required paths. Do not remove the user's real `G:\Project\bilinote` persistent directories or current production container.

- [ ] **Step 5: Run repository hygiene checks**

```powershell
git diff --check
git status --short
git log -5 --oneline
```

Expected: no uncommitted implementation files after the task commits.

---

### Task 5: Push and verify GitHub Actions / GHCR

**Files:**
- No new local code unless remote verification exposes a bounded defect.

**Interfaces:**
- Consumes: committed Tasks 1-4.
- Produces: public GHCR package that anonymous users can pull.

- [ ] **Step 1: Push `master` to the user's GitHub repository**

```powershell
git push origin master
```

Expected: push succeeds and triggers `Build and Publish Docker Image` from the `master` branch.

- [ ] **Step 2: Inspect the GitHub Actions result**

If GitHub CLI is authenticated:

```powershell
gh run list --workflow docker-build.yml --limit 5
$runId = gh run list --workflow docker-build.yml --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $runId --exit-status
```

Expected: build-and-push succeeds for both `linux/amd64` and `linux/arm64` and pushes a manifest.

If `gh` is unavailable or not authenticated, inspect the workflow run through GitHub web UI; do not claim success without the remote result.

- [ ] **Step 3: Verify the published package exists**

Run:

```powershell
docker manifest inspect ghcr.io/kiraliang954321/bilinote:latest
```

Expected: a manifest list including amd64 and arm64.

- [ ] **Step 4: Make the package Public if anonymous pull is denied**

On the first GHCR publication, set the package visibility to **Public** in GitHub package settings. This is an account/repository-side visibility action and cannot be inferred from a successful authenticated workflow push.

- [ ] **Step 5: Verify anonymous/public pull semantics**

Use a Docker context/session that is not relying on cached GitHub credentials if available, then run:

```powershell
docker pull ghcr.io/kiraliang954321/bilinote:latest
```

Expected: pull succeeds without requiring `docker login ghcr.io`.

- [ ] **Step 6: Verify release Compose against the published image**

Use an isolated project name and alternate port so the existing local BiliNote deployment is not disturbed:

```powershell
$env:APP_PORT="3016"
docker compose -p bilinote-release-e2e -f docker-compose.release.yml up -d
```

Verify:

```powershell
(Invoke-WebRequest http://localhost:3016 -UseBasicParsing).StatusCode
```

Expected: `200`.

Then clean only this verification stack:

```powershell
docker compose -p bilinote-release-e2e -f docker-compose.release.yml down -v
Remove-Item Env:APP_PORT
```

- [ ] **Step 7: Publish a versioned Docker release tag after `latest` passes**

Create the first Docker-only tag, for example:

```powershell
git tag docker-v1.0.0
git push origin docker-v1.0.0
```

Verify the workflow publishes:

```text
ghcr.io/kiraliang954321/bilinote:1.0.0
ghcr.io/kiraliang954321/bilinote:latest
ghcr.io/kiraliang954321/bilinote:sha-<当前提交短 SHA>
```

其中 SHA 标签的实际值从 workflow 输出或 `git rev-parse --short HEAD` 对照确认，不手工猜测。

- [ ] **Step 8: Final verification and handoff**

Record:

```text
master commit
workflow run URL / run id
GHCR package visibility = Public
latest manifest platforms
version tag
release Compose HTTP result
```

Update project handoff documentation only with verified results, then commit that documentation separately.
