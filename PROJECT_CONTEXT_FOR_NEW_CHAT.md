# BiliNote 本地改造项目——新聊天接续上下文

> 用途：把本文件内容直接复制到新的 ChatGPT 对话中，即可继续当前项目。
> 整理时间：2026-09-17
> 数学课程模式当前实现 checkpoint：`c4a56c5`
> 新聊天开始后必须重新核对真实 Git / Docker 状态，不要只依赖本文件中的时间点信息。

## 可直接复制到新聊天

```text
继续我的 BiliNote 本地改造项目，不要重新从头设计。

【项目位置】
部署根目录：G:\Project\bilinote
源码 Git 仓库：G:\Project\bilinote\source
Git 分支：master
数学课程模式当前实现 checkpoint：c4a56c5

新聊天开始后，请先真实执行：
- git status --short
- git branch --show-current
- git rev-parse --short HEAD
- docker compose ps
并读取：
- G:\Project\bilinote\source\MATH_COURSE_MODE_DESIGN.md
- G:\Project\bilinote\启动说明书.md

【已完成内容】
1. 已通过 Docker 部署 BiliNote。
   - 镜像：ghcr.io/jefferyhcool/bilinote:latest
   - 容器：bilinote
   - 访问：http://localhost:3015
   - restart: unless-stopped
   - 持久化目录：data / config / static / models

2. 已完成数学公式渲染修复。
   原问题：
   - 主笔记会收到 \(...\) / \[...\]，而默认 remark-math 主要识别 $...$ / $$...$$。
   - AI 问答区原来只有 remark-gfm，没有数学渲染链路。
   修复内容：
   - 显示阶段把 \(...\) 归一化为 $...$。
   - 显示阶段把 \[...\] 归一化为 $$...$$。
   - AI 问答加入 remark-math + rehype-katex。
   - 不修改原始 Markdown，只在渲染阶段转换。
   源码 checkpoint：9ae7243 fix(frontend): render LaTeX math in notes and chat

3. 当前部署使用“官方后端 + 本地前端覆盖层”。
   - 官方镜像仍提供 backend/nginx。
   - G:\Project\bilinote\frontend-dist 通过只读 volume 覆盖 /usr/share/nginx/html。
   - docker-compose.yml 中有：
     ./frontend-dist:/usr/share/nginx/html:ro
   - 数学公式修复已经实际部署。
   - HTTP 200、容器运行和持久化目录都已验证。

4. 已完成数学课程截图问题的真实调查和 RCA。
   已确认：
   - VideoReader 默认每 6 秒固定抽帧。
   - 当前抽帧去重只是 JPG MD5 exact match。
   - 老师每多写一笔，MD5 就不同，因此板书过程基本无法去重。
   - Screenshot Prompt 没有截图密度、板书完整度、相邻截图间隔等约束。
   - AI 输出 Screenshot-[mm:ss] 后，_insert_screenshots() 直接在该精确时间截帧。
   - 没有向后寻找“老师写完后的稳定帧”。
   - 一段约 7 分钟数学课程曾产生约 72 个 Screenshot marker，基本逐 6 秒枚举。
   - AI 常输出 *Screenshot-[mm:ss]*，当前 parser 不能完整消费尾部星号，因此页面可能出现孤立的 *。

5. 已完成并冻结“数学课程模式”改造设计。
   设计文档：
   G:\Project\bilinote\source\MATH_COURSE_MODE_DESIGN.md
   设计 checkpoint：
   1ac97e0 docs(math-course): design screenshot strategy

6. 已完成 WI-MATH-01 — Content Profile Contract。
   - 新增 content_profile=general|math_course，默认 general。
   - Web UI → API → backend → NoteGenerator → GPT/source identity 已完成透传。
   - checkpoint：4b5bf86 feat(math-course): add content profile contract

7. 已完成 WI-MATH-02 — Screenshot Intent Policy。
   - marker normalization 已完整消费 `*Screenshot-[mm:ss]*`。
   - math_course 连续 marker run 保留较晚 intent。
   - 同语义单元应用 45s min-gap。
   - hard cap = clamp(ceil(video_duration/75s), 1, 10)。
   - 超限时按章节代表 + 时间分布做 deterministic allocation，不简单取前 N 张。
   - checkpoint：8308296 feat(math-course): add screenshot intent policy

8. 已完成 WI-MATH-03 — Stable Frame Selector。
   - 搜索窗口 intent-2s 到 intent+8s，1s 采样。
   - 320x180 灰度分析；settled motion threshold=0.03；scene-cut threshold=0.18。
   - 选择优先级：settled → 更低 motion → 更高清晰度 → 更晚 timestamp。
   - forward scene cut 后不跨到下一页。
   - selector 失败回退原 intent timestamp；general 不做稳定帧搜索。
   - 22 个 focused/compatibility tests PASS。
   - checkpoint：60f22c3 feat(math-course): add stable frame selector

9. 已完成 WI-MATH-04 — Perceptual Sampling Dedupe。
   - general 保持原 exact-MD5 相邻去重行为。
   - math_course 改用相邻感知相似度：dHash Hamming <= 2 且 normalized grayscale mean delta <= 0.006。
   - 相似 visual-state cluster 保留最后一帧。
   - 只比较时间上相邻帧，避免误删隔很久后再次出现的相同板书。
   - 感知分析失败 fail-open：保留两帧并继续处理，不让可选去重优化阻断视频流程。
   - 27 个 focused/compatibility tests PASS。
   - checkpoint：81bc67d feat(math-course): add perceptual sampling dedupe

10. 已完成 WI-MATH-05 — Math Prompt + UI Preset。
   - `content_profile=math_course` 已真正进入 Prompt 构建链路；UniversalGPT 在正常 chunk、fallback chunk 与最终 chunk message 构建时均透传 profile。
   - math_course 普通公式、定义和推导优先使用 LaTeX/Markdown。
   - 仅在启用 `screenshot` format 时追加数学截图约束：优先完整题目、几何图、函数/坐标图、关键完整板书和必要完整页推导；避免连续 marker、逐时间点枚举和未完成书写状态；通常至少间隔 45 秒。
   - math_course 未启用截图时只保留 LaTeX-first 规则，不会注入 Screenshot marker 指令。
   - Web UI 选择 math_course 时显示“推荐配合学术风格”，但不会自动修改 `style`，保持两者独立。
   - Codex Review 发现并修复一次 bounded finding；fix 采用 TDD，先观察 RED 再 GREEN。
   - 最终相关 backend 回归：41 tests PASS；`py_compile` PASS；frontend production build PASS；`git diff --check` PASS。
   - checkpoint：c4a56c5 feat(math-course): add math prompt and ui preset

【当前架构】
部署目录本身不是 Git 仓库：
G:\Project\bilinote

真正的 Git 仓库：
G:\Project\bilinote\source

当前生产部署结构：
Docker official image
├─ official backend
├─ official nginx
└─ /usr/share/nginx/html
     ↑
     └─ G:\Project\bilinote\frontend-dist (read-only bind mount)

当前源码中的 math_course 最终截图链路：
video_interval 固定抽帧
→ VideoReader
→ grid_size 拼图
→ UniversalGPT 多模态输入
→ Prompt 输出 Screenshot intent
→ NoteGenerator._post_process_markdown()
→ ScreenshotPolicy（run collapse / 45s min-gap / hard cap）
→ StableFrameSelector（intent 邻域 settled frame 搜索）
→ generate_screenshot() 使用选定 timestamp
→ Markdown 插图

注意：上述后端源码链路尚未部署到当前官方 backend 容器；当前生产容器仍运行官方 backend。

核心原则：
AI 看多少帧 ≠ 最终笔记放多少图。
AI 指定的大致时间 ≠ 最终实际截帧时间。

【已确认决策】
1. 新增独立 content_profile：
   - general
   - math_course
   默认 general，保证旧客户端和现有行为兼容。

2. 不把数学逻辑塞进 style。
   推荐组合：
   content_profile = math_course
   style = academic

3. 数学内容优先级：
   LaTeX / Markdown
   > 完整题目与推导
   > 必要视觉截图
   > 装饰性/重复截图

4. 截图只优先用于：
   - 完整题目原图
   - 几何图
   - 函数图/坐标图
   - 关键完整板书
   - 有必要保留布局的一整页推导

5. 视觉采样和最终截图密度解耦。
   数学模式可以继续用约 6 秒视觉采样给 AI 看，但最终截图应稀疏。

6. 数学模式默认策略：
   analysis sample interval: 6s
   final screenshot min gap: 45s
   stable search before: 2s
   stable search after: 8s
   stable sample step: 1s

7. 必须新增 deterministic ScreenshotPolicy，不能只靠 Prompt。
   至少负责：
   - marker normalization
   - 连续 Screenshot marker run collapse
   - 最小时间间隔
   - 全局 hard cap

8. 连续 marker run 在数学板书场景中优先保留较晚 intent，因为通常越晚板书越完整。

9. hard cap 设计：
   max_screenshots = clamp(ceil(video_duration / 75s), 1, 10)
   约 7 分钟样本目标最终不超过约 6 张关键截图。

10. StableFrameSelector 首版不引入 OpenCV。
    使用现有依赖：
    - Pillow
    - numpy
    - ffmpeg
    当前 selector 分析：
    - motion delta
    - sharpness
    - scene cut
    参数：320x180 灰度、settled motion threshold=0.03、scene-cut threshold=0.18。
    dHash 留到 WI-MATH-04 的视觉采样感知去重，不混入最终截帧选择。

11. StableFrameSelector 失败时必须 fallback 到原 Screenshot intent timestamp，不能让整份笔记失败。

12. 感知去重首版必须保守，只比较相邻帧；相似帧簇保留最后一张，而不是第一张。

13. 首版明确不做：
    - OCR 板书识别
    - YOLO/专用黑板检测模型
    - 训练“是否写完”分类器
    - 自动学科识别
    - 数据库 screenshot policy 配置表
    - 旧笔记批量重写

【尚未解决的问题】
1. 后端自定义代码的生产部署方式还未最终冻结。
   当前 Docker 仍使用官方 backend，只覆盖前端。
   `WI-MATH-01/02/03/04/05` 已在源码仓库实现，但当前生产容器尚未运行这些 backend 改动。
   后续 Integration 必须明确：
   - 构建本地完整 Docker 镜像；或
   - 开发阶段 bind mount backend，稳定后再固化镜像。
   必须避免“source/backend 已改，但生产容器仍跑官方 backend”的假完成。

2. 感知相似度与稳定帧阈值尚未使用真实数学样本校准。
   StableFrameSelector 当前工程阈值：
   - scene-cut threshold = 0.18
   - settled motion threshold = 0.03
   Perceptual Sampling Dedupe 当前工程阈值：
   - dHash Hamming distance <= 2
   - normalized grayscale mean pixel delta <= 0.006
   这些阈值后续都需要用真实数学课程样本回归校准。

3. Windows 主机当前 PATH 中没有 ffmpeg。
   - Pillow/numpy 可用。
   - backend/Dockerfile 与 Dockerfile.complete 已安装 ffmpeg。
   - 因此 synthetic tests 可执行，但真实视频现场验证应在带 ffmpeg 的运行环境完成。

4. 真实 E2E 验收样本应正式记录 task/video baseline，包含：
   - 原 marker 数
   - 最终截图数
   - 哪些属于未写完板书
   - 哪些关键图必须保留

5. Browser extension 是否同步支持 content_profile 可后续决定；backend 已兼容旧插件不传字段时默认 general。

【下一步计划】
不要重新做 WI-MATH-01 ~ WI-MATH-05 的设计或实现，直接进入：
WI-MATH-06 — Real Math Course Acceptance

WI-MATH-06 目标：
- 先确定并部署真正包含 WI-MATH-01 ~ WI-MATH-05 的 backend runtime，不能继续使用官方旧 backend 做验收。
- 正式记录真实数学课程 baseline：video/task ID、原始 Screenshot marker 数、最终截图数、未写完板书、必须保留的关键图。
- 用约 7 分钟真实数学课程重新生成，目标最终截图 <= 6。
- 人工核对：无连续重复图、明显减少未写完板书、关键题目/几何图/函数图/完整板书仍保留、LaTeX 完整度不下降。
- 验证 general 模式无回归、Docker HTTP 200、data/config/static/models 持久化不受影响。

Integration 约束：
- WI-MATH-02/03/04 的核心逻辑可分别实现。
- 它们都会接入 backend/app/services/note.py，共享文件接线必须串行。
- pi_worker 服从单 active mutation gate，禁止 blind retry。

继续遵循 Phase 20 / Codex-Pi 工作流：
Codex 负责 Investigation / RCA / Architecture / Task Contract / Review / Integration / Acceptance。
非平凡可执行代码实现交给 pi_worker。
Pi 只负责 bounded implementation 和 focused self-test。
Codex Review 后如有 bounded findings，最多一次批量 pi_fix；不要一条问题一次 fix。

【最终验收目标】
当前失败基线：约 7 分钟课程 / 约 72 Screenshot intents。
目标：最终截图 <= 6。
同时要求：
- 无连续重复截图。
- 明显减少公式/板书只写一半的截图。
- 关键题目、几何图、完整板书仍保留。
- LaTeX 内容完整度不下降。
- general 模式不回归。
- Docker HTTP 200。
- data/config/static/models 持久化不受影响。

请从 WI-MATH-06 — Real Math Course Acceptance 开始工作。
```
