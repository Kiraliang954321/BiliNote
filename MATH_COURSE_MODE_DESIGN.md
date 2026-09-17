# BiliNote 数学课程模式改造设计

> 状态：Design / 未实施
> 基线：`master@9ae7243`
> 目标：为数学课程总结提供“公式优先、截图稀疏、完整板书优先”的专用模式，同时保持现有通用模式兼容。

## 1. 背景与真实问题

当前数学课程截图链路为：

```text
固定 video_interval 抽帧
→ 按 grid_size 拼图
→ 多模态模型看到网格图
→ 模型输出 *Screenshot-[mm:ss]
→ 后处理直接在 mm:ss 精确截一帧
→ 插入 Markdown
```

当前实现存在四个已验证问题：

1. `VideoReader` 按固定时间间隔抽帧，默认 6 秒。
2. 当前去重仅比较 JPG 文件 MD5，只有像素文件完全一致才去重；老师每多写一笔都会被视为新帧。
3. Screenshot Prompt 没有截图密度、完整板书、相邻截图间隔等约束。实际最新约 7 分钟数学视频生成了 72 个 Screenshot marker，基本逐 6 秒枚举。
4. `_insert_screenshots()` 直接使用模型给出的精确时间截帧，没有“向后等老师写完”的稳定帧选择。

另有一个独立格式缺陷：模型经常输出 `*Screenshot-[00:06]*`，而当前 marker regex 只消费前导 `*`，不消费尾部 `*`，最终页面会留下孤立的 `*`。

## 2. 设计原则

### 2.1 三条时间轴解耦

数学课程模式不再把“给 AI 看的帧”和“最终插进笔记的截图”视为同一件事。

```text
Visual Context Sampling
AI 理解视频用，允许较密

Screenshot Intent Selection
AI 只决定哪些知识点值得配图

Stable Frame Resolution
系统决定该知识点最终使用哪一帧
```

### 2.2 数学内容以结构化文本为主

优先级：

```text
LaTeX / Markdown
> 完整题目与推导
> 必要视觉截图
> 装饰性/重复截图
```

截图只承担 LaTeX 无法替代或不适合替代的信息，例如：

- 完整题目原图
- 几何图形
- 坐标图/函数图像
- 老师板书中的关键结构布局
- 一整页完整推导，用于对照

普通公式、定义、计算结果应优先转为 LaTeX，而不是截图。

### 2.3 通用模式零回归

新增可选 `content_profile`：

```text
general      # 默认，保持旧行为
math_course  # 数学课程专用行为
```

旧客户端不传该字段时继续走 `general`。

## 3. 目标架构

```text
NoteForm
│
├─ content_profile = general | math_course
├─ video_interval
└─ grid_size
        │
        ▼
VideoReader
│
├─ fixed interval sampling
├─ Math mode: conservative perceptual dedupe
│    └─ 相似帧簇保留“较晚状态”
└─ timestamped grids
        │
        ▼
UniversalGPT / Prompt Builder
│
├─ transcript
├─ visual context grids
└─ Math Screenshot Intent Rules
        │
        ▼
Markdown with Screenshot intents
        │
        ▼
ScreenshotPolicy
│
├─ normalize marker syntax
├─ collapse contiguous marker runs
├─ minimum-gap filtering
└─ density cap / section-aware preservation
        │
        ▼
StableFrameSelector
│
├─ search [ts-before, ts+after]
├─ scene-cut guard
├─ motion/stability score
├─ sharpness score
└─ choose settled complete frame
        │
        ▼
final screenshot
        │
        ▼
Markdown
```

## 4. UI / API 设计

### 4.1 前端

在“笔记风格”附近增加：

```text
内容模式
[ 通用 ] [ 数学课程 ]
```

`数学课程` 与现有 `学术` 风格不是同一概念：

- `style=academic` 决定文字表达风格。
- `content_profile=math_course` 决定公式与视觉截图策略。

用户仍可组合：

```text
content_profile = math_course
style = academic
```

这是推荐组合。

### 4.2 请求字段

新增后向兼容字段：

```python
content_profile: Literal["general", "math_course"] = "general"
```

不建议把数学模式塞进 `style`，否则未来物理/化学/编程课程的视觉策略也会继续污染“写作风格”语义。

### 4.3 数学模式默认策略

首版建议默认值：

```text
analysis sample interval: 6s
final screenshot min gap: 45s
stable search before: 2s
stable search after: 8s
stable sample step: 1s
contiguous marker run: keep latest intent
perceptual dedupe: conservative, adjacent only
```

注意：`video_interval=6` 只控制给 AI 的视觉上下文，不再决定最终截图密度。

## 5. Screenshot Prompt 设计

`math_course` 模式追加专用约束：

```text
数学课程截图规则：
1. 公式、定义、普通推导优先使用 LaTeX，不要用截图替代。
2. 只有题目原图、几何图、函数图、关键完整板书确实帮助理解时才插入 Screenshot marker。
3. 不要枚举每个可见时间点，也不要连续输出多个 Screenshot marker。
4. 同一知识点只选择一个最有代表性的截图时间。
5. 优先选择老师已经完成书写、画面内容完整的时间点。
6. 正在书写、擦除、切换页面、人物遮挡严重的中间状态不要选。
7. 相邻截图原则上至少间隔 45 秒；只有出现新的独立题目/图形时才可例外。
8. marker 必须独占一行，严格输出：*Screenshot-[mm:ss]
```

Prompt 是第一层约束，但不能作为唯一安全层。

## 6. ScreenshotPolicy：确定性截图稀疏化

新增纯逻辑组件 `ScreenshotPolicy`，在真正截帧前处理 Markdown 中的截图意图。

### 6.1 Marker normalization

统一接受：

```text
Screenshot-[01:23]
*Screenshot-[01:23]
*Screenshot-[01:23]*
Screenshot-01:23
```

替换时消费整个 marker，包括可选尾部 `*`，不再留下孤立星号。

### 6.2 连续 marker run 折叠

例如：

```text
*Screenshot-[02:00]*
*Screenshot-[02:06]*
*Screenshot-[02:12]*
*Screenshot-[02:18]*
```

视为一次“同一知识点的连续截图枚举”，数学模式只保留最后一个 intent：

```text
ScreenshotIntent(ts=138)
```

理由：对于板书课程，在同一连续段中更晚的帧通常比更早的帧包含更完整的书写状态。

### 6.3 Minimum gap

数学模式默认 `45s`。

如果两个独立 intent 小于 45 秒：

- 同一标题/段落范围内：优先保留后一个。
- 中间跨越新的 `##` / `###` 标题：允许保留，视为新的语义单元。

### 6.4 Global density guard

为防止模型异常再次输出几十张截图，增加 fail-safe 上限。

建议：

```text
max_screenshots = clamp(ceil(video_duration / 75s), 1, 10)
```

约 7 分钟视频：上限约 6 张。

超过全局上限时，不简单截断前 N 张，而是优先保证不同一级/二级章节至少有代表图，再按时间均匀分布补齐。

首版如果“章节公平分配”实现复杂，可先只实现 run collapse + min gap，并将 global cap 作为第二阶段；但最终验收应具备 deterministic hard cap。

## 7. StableFrameSelector：完整板书选择

当前：

```text
Screenshot-[03:30]
→ 截 03:30
```

数学模式改为：

```text
Screenshot-[03:30]
→ 搜索 03:28 ~ 03:38
→ 每 1s 取候选帧
→ 检测场景切换
→ 计算稳定度与清晰度
→ 选择“已经稳定”的最佳帧
```

### 7.1 不引入 OpenCV

当前后端已有：

- Pillow
- numpy
- ffmpeg

首版使用现有依赖即可完成，不新增大型 CV 依赖。

### 7.2 低成本帧特征

所有候选帧缩放到约 `320x180` 灰度图。

计算：

```text
motion_delta(t)
= mean(abs(frame[t] - frame[t-1])) / 255

sharpness(t)
= 灰度水平/垂直梯度能量

dHash(t)
= 64-bit difference hash
```

### 7.3 稳定帧条件

一个候选帧被视为“settled”需要：

```text
与前一帧变化较小
AND
与后一帧变化较小
AND
未跨越明显 scene cut
```

初始阈值不要散落在业务代码中，集中到 policy config，并通过真实数学视频回归校准。

### 7.4 选择策略

候选优先级：

```text
1. settled frame
2. 更低 motion score
3. 更高清晰度
4. 相同时更晚的 timestamp
```

“更晚 timestamp”只作为同等质量下的 tie-break，不允许跨过明显场景切换。

### 7.5 Scene-cut guard

若向后搜索时出现大幅画面跃迁，认为进入下一页/下一题：

```text
停止继续向后搜索
```

避免为了等“稳定”最后截到下一道题。

### 7.6 Fail-closed fallback

若稳定分析失败：

```text
fallback = 原 Screenshot intent timestamp
```

数学模式优化失败不能导致整份笔记失败。

## 8. Visual Context Perceptual Dedupe

这是给 AI 看的抽帧去重，与最终截图策略独立。

当前 MD5：

```text
只有文件字节完全相同才算重复
```

数学模式改为保守的相邻感知去重：

```text
adjacent dHash distance small
AND
pixel mean delta small
→ same visual state cluster
```

关键行为：

```text
相似帧簇不是“保留第一张”
而是“保留最后一张”
```

因为板书场景中最后一张往往信息最完整。

仅比较相邻帧，避免误删隔很久后再次出现的相同板书。

首版阈值必须保守，宁可多给 AI 一张，也不要误删新的公式/题目。

## 9. 数据与兼容性

### 9.1 新字段

`content_profile` 应进入：

- Frontend form schema/defaults/reset
- frontend API payload
- backend VideoRequest
- NoteGenerator.generate()
- GPTSource / prompt input（如果需要）
- screenshot post-processing policy selection

### 9.2 默认行为

```text
content_profile missing
→ general
→ 现有路径保持不变
```

因此旧任务、旧数据库记录、浏览器插件都不会因字段缺失而失败。

### 9.3 缓存 / checkpoint

因为 `content_profile` 会改变 Prompt 与截图后处理语义，涉及 GPT checkpoint/source signature 时必须纳入 identity，避免不同 profile 复用错误 checkpoint。

## 10. 文件边界建议

新增：

```text
backend/app/utils/frame_similarity.py
backend/app/services/screenshot_policy.py
backend/app/services/stable_frame_selector.py
```

修改：

```text
backend/app/utils/video_reader.py
backend/app/utils/screenshot_marker.py
backend/app/utils/video_helper.py
backend/app/services/note.py
backend/app/routers/note.py
backend/app/models/gpt_model.py              # 仅需要时
backend/app/gpt/prompt_builder.py
backend/app/gpt/universal_gpt.py             # source identity/profile forwarding
BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx
BillNote_frontend/src/constant/note.ts        # 如 UI 常量放这里
BillNote_frontend/src/services/note.ts
```

不需要修改：

```text
数据库 schema（首版不要求持久化独立策略表）
Docker 持久化目录
AI 问答索引
数学公式前端渲染补丁
```

## 11. Bounded WorkItems

### WI-MATH-01 — Content Profile Contract

**Goal**
新增 `content_profile=general|math_course`，默认 general，完成前后端透传，不改变截图行为。

**Relevant / Allowed**

- `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
- `BillNote_frontend/src/services/note.ts`
- 必要 frontend type/constant 文件
- `backend/app/routers/note.py`
- `backend/app/services/note.py`
- `backend/app/gpt/universal_gpt.py` / model，仅限 profile forwarding / source identity
- focused tests

**Acceptance**

- 不传字段时与当前行为一致。
- math_course 字段从 UI 到 NoteGenerator 可观察。
- checkpoint/source signature 不会跨 profile 错误复用。

**Risk**：Low/Medium。

---

### WI-MATH-02 — Screenshot Intent Policy

**Depends on**：WI-MATH-01。

**Goal**
实现 marker normalization、连续 marker run collapse、45s min-gap 与 deterministic density guard。

**Allowed**

- `backend/app/utils/screenshot_marker.py`
- `backend/app/services/screenshot_policy.py`（new）
- `backend/tests/test_screenshot_marker.py`
- `backend/tests/test_screenshot_policy.py`（new）
- `backend/app/services/note.py` 仅接入 policy

**Acceptance**

- `*Screenshot-[01:02]*` 被完整消费，无孤立 `*`。
- 连续 6 秒 marker run 只保留一个，保留较晚 intent。
- 数学模式 min-gap 生效；general 不受影响。
- 7 分钟/72 marker 级异常输入最终不会产生几十张截图。

**Risk**：Medium，主要风险为过度删图。

---

### WI-MATH-03 — Stable Frame Selector

**Depends on**：WI-MATH-01，可在逻辑上与 WI-MATH-02 独立设计，但 Integration 需串行。

**Goal**
截图 intent 不再直接等于最终截帧时刻；数学模式在邻域搜索 settled frame。

**Allowed**

- `backend/app/services/stable_frame_selector.py`（new）
- `backend/app/utils/video_helper.py`
- `backend/app/services/note.py` 仅接入 selector
- focused tests

**Acceptance**

- synthetic “持续书写→停止”序列选择停止后的稳定帧。
- scene cut 后不越界选择下一页。
- selector 失败时回退原 timestamp，不阻断笔记生成。
- general 仍按原 timestamp 截图。

**Risk**：Medium。

---

### WI-MATH-04 — Perceptual Sampling Dedupe

**Depends on**：WI-MATH-01。

**Goal**
数学模式把 MD5 exact dedupe 升级为保守感知去重，相似簇保留最后状态。

**Allowed**

- `backend/app/utils/frame_similarity.py`（new）
- `backend/app/utils/video_reader.py`
- `backend/tests/test_video_reader_dedupe.py`
- 新增 focused similarity tests

**Acceptance**

- 完全相同帧仍去重。
- 轻微编码/微小像素变化可被识别为同一视觉状态。
- 相似帧簇保留较晚帧。
- 明显新增公式/换页不得被误删。
- 不新增 OpenCV/skimage 等大依赖。

**Risk**：Medium/High，阈值需要真实样本回归。

---

### WI-MATH-05 — Math Prompt + UI Preset

**Depends on**：WI-MATH-01，建议在 Policy contract 冻结后完成。

**Goal**
在 UI 中提供“数学课程”，Prompt 明确 LaTeX 优先、截图稀疏、完整板书优先。

**Allowed**

- `backend/app/gpt/prompt_builder.py`
- frontend NoteForm / constants
- focused tests

**Acceptance**

- math_course Prompt 包含明确截图约束。
- general Prompt 不新增数学限制。
- UI 可选择并恢复 profile。
- 推荐组合仍允许 `math_course + academic`。

**Risk**：Low。

---

### WI-MATH-06 — Real Math Course Acceptance

**Depends on**：WI-MATH-02/03/04/05。

**Goal**
使用现有本地数学课程视频做真实端到端验收。

**Acceptance baseline**

以当前约 7 分钟样本为例：

```text
旧结果：72 Screenshot intents / 逐 6 秒大量重复
目标：最终截图 <= 6（默认策略）
```

并人工核对：

- 没有连续重复截图。
- 没有明显“公式只写了一半”的选图。
- 题目/几何图等重要视觉信息仍至少保留代表图。
- LaTeX 内容完整性不因减少截图而下降。
- HTTP / Docker / 持久化行为不回归。

## 12. Scheduler / 实施顺序

推荐依赖：

```text
WI-MATH-01 Contract
      │
      ├── WI-MATH-02 Screenshot Policy
      ├── WI-MATH-03 Stable Frame Selector
      ├── WI-MATH-04 Perceptual Dedupe
      └── WI-MATH-05 Prompt/UI
               │
               ▼
        Serial Integration
               │
               ▼
        WI-MATH-06 Real E2E
```

从文件冲突角度，02/03/04 的核心新文件可以独立；但都需要少量接入 `note.py`，Integration 时必须串行处理接线，不能让多个 Worker 同时修改该共享文件。

实际 Pi 调度还必须服从当前 `pi_worker` 的 active-mutation gate；即使 WorkGraph 逻辑可并行，也不能绕过实际 Worker 的单 mutation 安全约束。

## 13. 验证分层

### L1 Focused

- marker parser tests
- screenshot policy tests
- stable selector synthetic tests
- perceptual dedupe tests
- profile forwarding tests
- prompt tests

### L2 Codex Focused Verification

- 受影响 backend tests
- frontend build/type/lint（按项目现有可运行命令）
- git diff / diff check

### L3 Integration

- NoteGenerator screenshot post-process integration
- profile=general regression
- profile=math_course integration

### L4 Real Acceptance

对现有数学视频重新生成一次：

- 对比 screenshot count
- 对比截图时间与板书完整性
- 验证公式渲染
- Docker HTTP 200
- data/config/static/models 不丢失

## 14. 不在首版范围

暂不做：

- OCR 识别板书文字
- YOLO/专门黑板检测模型
- 训练视觉分类器判断“老师是否写完”
- 数据库级 screenshot policy 配置表
- 自动识别学科为数学
- 对旧笔记批量重写截图

原因：当前问题可由低成本 deterministic CV + Prompt + Policy 三层解决，先验证效果，再决定是否需要更重的视觉模型。

## 15. 预期结果

当前：

```text
6 秒一帧
→ AI 基本全选
→ 7 分钟几十张截图
→ 很多写到一半
```

目标：

```text
6 秒视觉上下文仍可保留
→ AI 只表达“这里值得有图”
→ Policy 去掉重复/过密 intent
→ StableFrameSelector 向附近寻找完整板书
→ 7 分钟约 4~6 张关键截图
→ 公式主体由 LaTeX 承担
```

数学课程模式最终应做到：

> **让 AI 看得足够多，但让笔记只留下真正值得看的图。**
