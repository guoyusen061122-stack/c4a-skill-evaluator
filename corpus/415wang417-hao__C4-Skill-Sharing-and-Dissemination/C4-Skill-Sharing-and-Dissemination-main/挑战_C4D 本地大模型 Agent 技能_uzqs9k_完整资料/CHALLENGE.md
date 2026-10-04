# Challenge C4D：本地大模型 Agent 技能（Local LLM Agent Skills with Gemma 4）

> 🔥 C4 的硬核分支——不依赖云端 API，在你自己的电脑上跑大模型，驱动 Agent 技能。
> 本质：证明你能在**本地设备**上运行一个有真实能力的 LLM Agent——不花一分钱 API 费用。

---

## ⚠️ 核心挑战：在你自己的设备上运行 Agent

Google 刚刚发布了 **Gemma 4**——四款开源模型，Apache 2.0 协议，专为本地运行和 Agent 工作流设计。

**你的任务：**

1. **在你的电脑/手机上下载并运行** Gemma 4 模型
2. **用本地模型驱动 Agent 技能**——执行函数调用、生成结构化输出、完成多步任务
3. **生成一个交互式地图**——展示 SIAS University（郑州西亚斯学院）或其他有意义的地点
4. **截图/录屏发群里**证明是在本地跑的

> 💡 为什么要本地跑？因为**数据主权**和**零成本推理**是 AI 工程师的核心能力。云端 API 会断、会涨价、会审查——但你本地的模型永远属于你。

---

## 📊 Gemma 4 家族：四款模型，你跑哪个？

Gemma 4 有四款模型，**你必须在提交中明确标注你跑的是哪一款**：

| 模型 | 参数量 | 活跃参数 | 最低内存（4-bit） | 上下文长度 | 适合设备 |
|------|--------|----------|-------------------|-----------|----------|
| **Gemma 4 E2B** | ~2B effective | 2B | ~5 GB | 128K | 手机、树莓派、老旧笔记本 |
| **Gemma 4 E4B** | ~4.5B effective | 4.5B | ~5 GB | 128K | 普通笔记本（推荐入门） |
| **Gemma 4 26B MoE** | 26B total | 3.8B active | ~18 GB | 256K | 16GB+ 显存 GPU 或 24GB+ Mac |
| **Gemma 4 31B Dense** | 31B | 31B | ~20 GB | 256K | 24GB+ 显存 GPU 或 32GB+ Mac |

> ⚠️ **你必须标注你用的是哪个模型 + 什么量化方式（如 Q4_K_M）+ 在什么设备上跑的。** 这是评审的关键信息。

**所有四款模型都支持：** 多模态（文本+图像）、原生函数调用（function calling）、系统提示、结构化 JSON 输出、Agent 工作流。

---

## 🎯 你要做什么

### 核心任务：本地 Agent + 交互式地图

在你的设备上用 Gemma 4 完成以下流程：

```
本地 Gemma 4 模型
    ↓
接收用户指令："给我生成一个 SIAS University 周边的地图"
    ↓
Agent 调用函数/工具：查询地点信息、生成坐标数据
    ↓
生成交互式 HTML 地图（Leaflet.js / Folium / 其他）
    ↓
在浏览器中打开 → 截图/录屏发群
```

**地图要求：**
- 必须包含 **SIAS University（郑州西亚斯学院）** 或你选择的其他有意义的地点
- 必须是**交互式**的（可缩放、可点击标记）
- 标记点必须包含有意义的信息（地点名称、描述、坐标）
- 地点数据必须由**本地 Gemma 4 模型生成**（不是你手写的 JSON）

**Agent 技能要求：**
- 模型必须通过**函数调用（function calling）**或**结构化输出**来生成地图数据
- 必须展示至少一个 Agent 能力：工具调用、多步推理、代码生成、或数据结构化

---

## 📦 推荐技术栈

### 运行 Gemma 4 的方式

| 方案 | 难度 | 说明 |
|------|------|------|
| **Ollama**（推荐） | ★ | 一行命令跑起来，自带 OpenAI 兼容 API |
| **LM Studio** | ★ | GUI 界面，拖拽下载模型，适合非 CS 专业 |
| **llama.cpp** | ★★ | 最底层，性能最优，需要编译 |
| **Unsloth Studio** | ★★ | 网页 UI，支持微调 |
| **AI Edge Gallery** | ★★ | Google 官方手机端运行方案 |

### 快速开始（Ollama）

```bash
# 1. 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh   # Linux/Mac
# Windows: 从 ollama.com 下载安装包

# 2. 下载 Gemma 4（选一个适合你设备的）
ollama run gemma4:e2b    # 最小，手机/老电脑都能跑
ollama run gemma4:e4b    # 推荐入门，普通笔记本
ollama run gemma4:26b    # MoE，需要 16GB+ 内存
ollama run gemma4:31b    # 最强，需要 24GB+ 内存

# 3. 验证 function calling
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4",
    "messages": [{"role": "user", "content": "List 5 landmarks near SIAS University in JSON format"}]
  }'
```

### 生成交互式地图的方式

| 方案 | 语言 | 说明 |
|------|------|------|
| **Folium** | Python | `pip install folium`，最简单的交互式地图 |
| **Leaflet.js** | HTML/JS | 纯前端，生成 HTML 文件直接打开 |
| **Plotly** | Python | 支持 Mapbox，更花哨 |
| **Deck.gl** | JS | 3D 地图可视化 |

### 最简示例（Python + Ollama + Folium）

```python
import requests, json, folium

# 1. 用本地 Gemma 4 生成地点数据
response = requests.post("http://localhost:11434/v1/chat/completions", json={
    "model": "gemma4",
    "messages": [
        {"role": "system", "content": "You are a geography assistant. Always respond with valid JSON only."},
        {"role": "user", "content": """List 8 notable locations at or near SIAS University (西亚斯学院) 
         in Xinzheng, Henan, China. Return JSON array with fields: 
         name, name_zh, latitude, longitude, description"""}
    ]
})

# 2. 解析模型输出
data = json.loads(response.json()["choices"][0]["message"]["content"])

# 3. 生成交互式地图
m = folium.Map(location=[34.40, 113.73], zoom_start=14)
for loc in data:
    folium.Marker(
        [loc["latitude"], loc["longitude"]],
        popup=f"<b>{loc['name_zh']}</b><br>{loc['description']}",
        tooltip=loc["name"]
    ).add_to(m)
m.save("sias_map.html")
print("地图已生成：sias_map.html")
```

---

## 🎯 四级任务

### Level 1：本地跑通 Gemma 4（Bronze 🥉）

> **在你的设备上成功运行 Gemma 4 并完成基本对话。**

- 安装 Ollama 或 LM Studio
- 下载任意一款 Gemma 4 模型
- 成功运行并截图证明（包含模型名称、设备信息）
- 让模型生成一段关于 SIAS University 的介绍文字

**交付：** 运行截图 + 设备信息 + 模型版本

---

### Level 2：Agent 函数调用 + 交互式地图（Silver 🥈）

> **用本地 Gemma 4 的 Agent 能力生成交互式地图。**

- 通过 Ollama API 或 function calling 让模型生成结构化地点数据
- 用 Folium / Leaflet.js 渲染交互式地图
- 地图包含 SIAS University 及周边至少 5 个标记点
- 每个标记点有名称、描述、坐标

**交付：** 交互式地图 HTML + 生成地图的完整代码 + 模型输出日志

---

### Level 3：完整 Agent 技能包（Gold 🥇）

> **构建一个可复用的本地 Agent 技能，不仅仅是地图。**

在 Level 2 基础上，展示更深层的 Agent 能力：

| 扩展方向 | 说明 |
|----------|------|
| 多轮对话 Agent | 用户可以交互式地添加/修改地图标记 |
| 多工具调用 | 模型调用多个函数（查天气、查路线、查评分等） |
| 代码生成 Agent | 模型自动生成 Python/JS 代码并执行 |
| 视觉理解 | 给模型一张校园照片，让它识别并标注在地图上 |
| 多语言地图 | 中英文双语标注 + 多语言描述 |

**交付：** 完整技能包（可打包为 .skill 或 GitHub repo）+ 演示录屏

---

### Level 4：极限优化 + 设备适配（Platinum 💎）

> **把本地 Agent 推到极限——不同设备、不同模型、极致优化。**

在 Level 3 基础上，选择至少两项：

- **模型对比报告**：E2B vs E4B vs 26B vs 31B 在 Agent 任务上的表现对比（速度、质量、内存）
- **设备适配**：在手机（AI Edge Gallery）、笔记本、台式机上分别跑通
- **🔥 Uncensored 模型（加分）**：运行一个无审查版本（如社区微调的 uncensored 变体），对比默认模型在 Agent 任务上的差异
- **量化对比**：同一模型不同量化级别（Q4 vs Q8 vs FP16）的质量/速度权衡
- **性能调优**：context length、batch size、GPU offload 等参数调优文档

**交付：** 完整技术报告 + 多设备/多模型对比数据 + GitHub repo

---

## 🌟 特别激励：非计算机专业优先

> **🏆 首个完成 Level 2 的非计算机专业同学，直接获得 C4 最高评级。**

C4D 的意义不仅是技术挑战——它证明**任何专业的学生都能掌握本地 AI 部署**。无论你是金融、设计、教育还是医学专业，你都应该能在自己的设备上运行 AI。

非 CS 同学推荐路径：
1. 安装 **LM Studio**（图形界面，零命令行）
2. 搜索下载 **Gemma 4 E4B**（最适合笔记本）
3. 用 LM Studio 内置聊天生成地点 JSON
4. 复制粘贴到简单的 Python 脚本生成地图

---

## 📎 需要提交什么

```
姓名_C4D_方案设计.md              ← 架构、设备信息、选了哪个 Gemma 4 模型及原因
姓名_C4D_agent-skill/             ← 你的 Agent 技能代码（或源码 zip）
姓名_C4D_map.html                 ← 生成的交互式地图
姓名_C4D_output_screenshots/      ← 运行截图（必须包含模型名称+设备信息）
姓名_C4D_验证报告.md              ← 模型输出质量评估 + 设备性能数据
姓名_C4D_教学说明.md              ← 怎么安装、怎么复现
姓名_C4D_AI日志.md（必须）        ← AI 使用全过程。无此项无法评审。
姓名_C4D_拿来说明.md              ← 用了哪些库/工具、参考了什么
```

**⚠️ 截图/录屏中必须清晰显示以下信息：**
1. 运行的 Gemma 4 模型名称及版本（如 `gemma4:26b-a4b-q4_K_M`）
2. 运行工具（如 Ollama v0.20.2）
3. 设备信息（CPU/GPU、内存、操作系统）
4. 模型实际运行中的推理速度（tok/s）

---

## 评审标准

| 维度 | 权重 | 说明 |
|------|------|------|
| **本地运行验证** | 25% | 确实在本地跑起来了？截图/录屏是否充分证明？ |
| **Agent 能力展示** | 25% | 函数调用、结构化输出、多步推理——展示了多少 Agent 能力？ |
| **地图质量** | 20% | 交互性、标记点数量与质量、视觉效果 |
| **完成级别** | 15% | Level 1–4 到哪一级？ |
| **可复用性** | 15% | 别人照着你的教学说明能跑通吗？ |

---

## 起步指南

### Step 1：确认你的设备能跑什么（Day 1）

查看你的设备配置：

| 你的设备 | 推荐模型 | 运行方式 |
|----------|----------|----------|
| 8GB 内存笔记本 | Gemma 4 E2B | Ollama / LM Studio |
| 16GB 内存笔记本 | Gemma 4 E4B | Ollama / LM Studio |
| 16GB 显存 GPU（如 RTX 4080） | Gemma 4 26B MoE | Ollama |
| 24GB+ Mac / 24GB 显存 GPU | Gemma 4 31B Dense | Ollama |
| Android/iOS 手机 | Gemma 4 E2B/E4B | AI Edge Gallery |

### Step 2：安装 + 下载模型（Day 1）

```bash
# 方案 A：Ollama（推荐）
curl -fsSL https://ollama.com/install.sh | sh
ollama run gemma4:e4b   # 或你选择的版本

# 方案 B：LM Studio（图形界面）
# 从 lmstudio.ai 下载，搜索 Gemma 4，一键下载
```

### Step 3：验证 Agent 能力（Day 2–3）

测试函数调用和结构化输出：

```bash
# 测试结构化 JSON 输出
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemma4",
    "messages": [
      {"role": "system", "content": "Always respond in valid JSON only."},
      {"role": "user", "content": "List 3 landmarks near SIAS University with name, lat, lng, description"}
    ]
  }'
```

### Step 4：生成交互式地图（Day 3–5）

用模型输出的数据生成 Folium / Leaflet 地图。

### Step 5：打包提交（Day 6–7）

截图、录屏、写文档、提交。

---

## 参考资源

| 资源 | 说明 |
|------|------|
| [Ollama Gemma 4 页面](https://ollama.com/library/gemma4) | 官方 Ollama 模型页，含所有变体 |
| [Gemma 4 官方博客](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/) | Google 发布文章，介绍四款模型 |
| [Unsloth Gemma 4 本地运行指南](https://unsloth.ai/docs/models/gemma-4) | 详细硬件需求 + llama.cpp 设置 |
| [Gemma 4 硬件选购指南](https://www.compute-market.com/blog/gemma-4-local-hardware-guide-2026) | 各模型 VRAM 需求对比 |
| [LM Studio](https://lmstudio.ai/) | 图形界面本地模型运行器 |
| [AI Edge Gallery](https://ai.google.dev/edge) | Google 官方手机端运行方案 |
| [Folium 文档](https://python-visualization.github.io/folium/) | Python 交互式地图库 |
| [Leaflet.js](https://leafletjs.com/) | 最流行的 JS 交互式地图库 |

---

## 🔥 加分项：Uncensored 模型

Gemma 4 默认模型有内容安全过滤。社区已经开始发布**去审查微调版本（uncensored variants）**。

如果你能：
1. 找到并运行一个 Gemma 4 uncensored 变体
2. 对比默认模型与 uncensored 模型在相同 Agent 任务上的表现差异
3. 写一份对比报告（输出质量、拒绝率、任务完成率）

——这将作为**显著加分项**。

> ⚠️ Uncensored 不意味着有害。它意味着模型不会无理由拒绝正常请求（如生成特定地区的历史信息、讨论敏感但合法的学术话题）。你需要在报告中负责任地讨论这个话题。

---

## 为什么 C4D 值得做

```
C4  = 我会做一个技能
C4A = 我会评审所有人的技能
C4B = 我会做内容发布流水线
C4C = 我会做端到端自动化系统
C4D = 我能在自己的设备上运行 AI Agent——不依赖任何云服务
```

C4D 训练的是**AI 自主权**——

- **隐私：** 你的数据不离开你的设备
- **成本：** 零 API 费用，无限推理
- **自由：** 不受平台审查和服务中断影响
- **理解：** 你真正理解模型是怎么跑起来的，不是黑盒调 API

想象一下：你在飞机上、在没有网络的教室里、在任何地方——打开笔记本电脑，本地模型立刻可用。这就是 **AI 数字主权**。

---

> 📣 **C4D 的终极价值：**
>
> 云端 AI 是租来的能力。本地 AI 是你拥有的能力。
> C4D 证明你不仅会*使用* AI，你还会*部署* AI。
> 一台笔记本 + 一个开源模型 + 你的工程能力 = 完全自主的 AI Agent。
> **🏆 首个完成的非计算机专业同学，直接获得 C4 最高评级。**
