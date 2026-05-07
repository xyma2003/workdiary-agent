# AI 求职助手 (Job Assistant)

> 粘贴简历 + JD，4 个 AI Agent 自动协作，生成定制简历、Cover Letter 和评分报告。

---

## 项目介绍

AI 求职助手是一个基于多 Agent 协作框架（CrewAI）构建的求职辅助工具。你只需要把原始简历和目标职位的 JD（职位描述）粘贴进去，系统会依次启动 4 个专职 AI Agent，完成从 JD 解析、简历改写、Cover Letter 撰写到整体评分的完整流程，最终输出一套针对该岗位高度定制的求职材料。

### 架构图

```
用户输入
  ├── 原始简历（Markdown / 纯文本）
  └── 目标 JD

          │
          ▼
┌─────────────────────────────────────────────────────┐
│                  CrewAI Sequential Pipeline          │
│                                                     │
│  Step 1                  Step 2                     │
│  ┌─────────────────┐    ┌─────────────────────┐    │
│  │  Research Agent │───>│  Rewrite Agent       │    │
│  │  (Haiku)        │    │  (Sonnet)            │    │
│  │                 │    │                      │    │
│  │  · 解析 JD      │    │  · 改写简历          │    │
│  │  · 提取关键词   │    │  · 镜像 JD 语言      │    │
│  │  · 识别 ATS 词  │    │  · 强化量化成就      │    │
│  └─────────────────┘    └─────────────────────┘    │
│                                  │                  │
│  Step 3                  Step 4  │                  │
│  ┌─────────────────┐    ┌────────▼────────────┐    │
│  │  Cover Letter   │    │  Review Agent        │    │
│  │  Agent (Sonnet) │───>│  (Haiku)             │    │
│  │                 │    │                      │    │
│  │  · 写求职信     │    │  · ATS 关键词核查    │    │
│  │  · 3-4 段结构   │    │  · 经历匹配度评估    │    │
│  │  · 人性化语气   │    │  · 0-100 综合评分    │    │
│  └─────────────────┘    └─────────────────────┘    │
│                                                     │
└─────────────────────────────────────────────────────┘
          │
          ▼
     Streamlit UI（4 个 Tab 展示 + 下载按钮）
          │
          ▼
     output/ 目录（4 个 .md 文件持久化）
```

---

## 技术栈

| 组件 | 版本 / 说明 |
|------|------------|
| **CrewAI** | 1.14.4 — 多 Agent 编排框架，顺序流水线 |
| **Claude Haiku** | `claude-haiku-4-5-20251001` — 用于 Research Agent 和 Review Agent（速度快、成本低） |
| **Claude Sonnet** | `claude-sonnet-4-5` — 用于 Rewrite Agent 和 Cover Letter Agent（写作质量更高） |
| **Streamlit** | UI 框架，双栏输入 + 4 Tab 结果展示 |
| **python-dotenv** | 从 `.env` 文件加载 API Key |
| **LiteLLM** | CrewAI 内部调用 Anthropic API 的适配层（`anthropic/` 前缀格式） |

---

## 快速开始

### 前提条件

- Python 3.10 或更高版本
- Anthropic API Key（在 [console.anthropic.com](https://console.anthropic.com/) 申请）
- 稳定的网络连接（需访问 Anthropic API）

### 安装步骤

**1. 克隆仓库（或进入项目目录）**

```bash
cd job-assistant
```

**2. 创建并激活虚拟环境（推荐）**

```bash
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

**3. 安装依赖**

```bash
pip install -r requirements.txt
```

### 配置

在项目根目录创建 `.env` 文件，写入你的 API Key：

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
```

> `.env` 文件已在 `.gitignore` 中排除，不会被提交到 Git。

### 启动

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

---

## 使用方法

**第一步：粘贴简历**

在左侧文本框粘贴你的完整简历。支持纯文本或 Markdown 格式。建议保留原始结构（教育、工作经历、技能等分节），Agent 会依据此结构进行改写。

**第二步：粘贴目标 JD**

在右侧文本框粘贴目标职位的完整 JD，包括岗位描述、任职要求、加分项等全部内容。内容越完整，分析越准确。

**第三步：点击「开始分析」**

点击蓝色「🚀 开始分析」按钮。页面会显示旋转进度条，提示「4 个 Agent 正在协作分析中，预计需要 1–2 分钟」。

> 实际耗时取决于简历/JD 长度以及 API 响应速度，通常在 60–120 秒之间。

**第四步：查看 4 个 Tab 的结果**

分析完成后，结果以 4 个 Tab 展示：

| Tab | 内容 |
|-----|------|
| 📋 JD 分析 | 必备技能、加分技能、核心职责、企业文化信号、ATS 关键词、潜在红旗 |
| 📄 定制简历 | 针对该 JD 改写后的完整简历（Markdown 格式，可直接复制） |
| ✉️ Cover Letter | 3–4 段个性化求职信，连接你的具体经历与 JD 要求 |
| ⭐ 评分报告 | 关键词匹配度、经历相关度、求职信质量、Top 3 改进建议、综合匹配分（0–100） |

**第五步：下载文件**

每个 Tab 底部均有「下载」按钮，可将对应内容保存为 `.md` 文件，同时文件也会自动保存到项目 `output/` 目录。

---

## 4 个 Agent 详细说明

### Agent 1 — Research Agent（JD 分析师）

| 属性 | 值 |
|------|-----|
| Role | `Job Description Analyst` |
| 模型 | Claude Haiku（速度优先，成本低） |
| max_tokens | 2048 |
| 输入 | 用户粘贴的 JD 原文 |
| 输出 | `output/jd_analysis.md` |

**职责：** 扮演拥有 10 年经验的高级招聘官，精准拆解 JD。提取：

1. 必备技能与经验（硬性要求）
2. 加分项（Nice-to-have）
3. 核心职责
4. 企业文化信号（团队协作风格、工作节奏等）
5. **ATS 关键词**（简历必须包含才能通过系统筛选的词汇）
6. 红旗警示（不寻常的要求或潜在问题）

---

### Agent 2 — Rewrite Agent（简历改写专家）

| 属性 | 值 |
|------|-----|
| Role | `Resume Tailoring Specialist` |
| 模型 | Claude Sonnet（写作质量优先） |
| max_tokens | 4096 |
| 输入 | 原始简历 + Research Agent 的分析结果（上下文传递） |
| 输出 | `output/tailored_resume.md` |

**职责：** 扮演帮助 500+ 候选人拿到 Top 科技公司面试的简历撰写专家，遵循严格规则：

- 镜像 JD 语言，嵌入 ATS 关键词
- 按相关度重新排序经历条目
- 强化量化成就表述（STAR 结构）
- **绝不虚构任何经历、技能或数据**，仅重新表述已有内容

---

### Agent 3 — Cover Letter Agent（求职信撰写师）

| 属性 | 值 |
|------|-----|
| Role | `Cover Letter Writer` |
| 模型 | Claude Sonnet（写作质量优先） |
| max_tokens | 2048 |
| 输入 | JD 分析 + 定制简历（上下文传递） |
| 输出 | `output/cover_letter.md` |

**职责：** 扮演专注于求职材料的专业写作者，输出结构如下：

1. **开头段**：用真诚的方式展示对该职位的兴趣，而非千篇一律的「I am writing to apply」
2. **正文（2 段）**：将 2–3 段具体经历与 JD 要求直接挂钩，有故事、有数据
3. **结尾段**：清晰的行动号召（Call to Action）

语气要求：专业但有人情味，避免模板化套话。

---

### Agent 4 — Review Agent（质量评审官）

| 属性 | 值 |
|------|-----|
| Role | `Application Quality Reviewer` |
| 模型 | Claude Haiku（速度优先，成本低） |
| max_tokens | 1024 |
| 输入 | 全部三个前序 Task 的输出（通过 `context` 参数传入） |
| 输出 | `output/review.md` |

**职责：** 扮演每天审阅数百份申请的招聘经理，给出不留情面的诚实反馈：

1. 简历-JD 关键词匹配度（ATS 关键词是否全部命中）
2. 经历相关度（经历是否真正匹配岗位需求）
3. 求职信质量（是否有说服力、具体、有人情味）
4. 整体短板（缺什么、哪里弱）
5. 提交前 Top 3 改进建议
6. **综合匹配评分（0–100）**

---

## 输出文件说明

所有输出保存在项目根目录的 `output/` 文件夹下：

```
output/
├── jd_analysis.md       # JD 结构化分析（Research Agent 输出）
├── tailored_resume.md   # 定制化简历（Rewrite Agent 输出）
├── cover_letter.md      # 求职信（Cover Letter Agent 输出）
└── review.md            # 评分报告（Review Agent 输出）
```

| 文件 | 内容结构 |
|------|---------|
| `jd_analysis.md` | Required Skills / Nice-to-Have / Responsibilities / Culture / ATS Keywords / Red Flags |
| `tailored_resume.md` | 完整 Markdown 格式简历，经历条目已按 JD 相关度重排并改写 |
| `cover_letter.md` | 3–4 段求职信，可直接复制使用 |
| `review.md` | 各维度评估 + Top 3 改进建议 + 最终 0–100 分 |

> 每次运行会覆盖同名文件。如需保留多个版本，请在运行前手动备份 `output/` 目录。

---

## 项目结构

```
job-assistant/
├── app.py                  # Streamlit 前端入口，UI 布局与结果展示
├── crew.py                 # CrewAI Pipeline 核心逻辑，定义 Tasks 和 Crew
├── config.py               # 全局配置（API Key、模型名、输出目录）
├── requirements.txt        # Python 依赖
├── .env                    # API Key（需自行创建，不提交 Git）
│
├── agents/
│   ├── __init__.py         # 统一导出 4 个 make_*_agent 工厂函数
│   ├── research_agent.py   # Research Agent 定义（Haiku）
│   ├── rewrite_agent.py    # Rewrite Agent 定义（Sonnet）
│   ├── cover_letter_agent.py  # Cover Letter Agent 定义（Sonnet）
│   └── review_agent.py     # Review Agent 定义（Haiku）
│
├── tools/                  # 预留目录（自定义 CrewAI Tools 扩展用）
├── assets/                 # 预留目录（静态资源，如 logo 等）
└── output/                 # 自动生成，存放 4 个输出 .md 文件
```

---

## 常见问题

**Q: 运行时报错 `ANTHROPIC_API_KEY` 未设置或无效**

确认项目根目录有 `.env` 文件，且内容格式正确：

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxx
```

注意 Key 前后不要有引号或多余空格。重新启动 `streamlit run app.py` 使配置生效。

---

**Q: 点击「开始分析」后长时间无响应或超时**

- 4 个 Agent 顺序运行，每个 Agent 都需要等待 API 响应，总耗时通常为 60–120 秒。
- 如果超过 3 分钟仍未完成，检查网络连接，或确认 Anthropic API 服务状态（[status.anthropic.com](https://status.anthropic.com/)）。
- Streamlit 界面的 Spinner 消失即表示完成。

---

**Q: 报错 `crewai` 版本不兼容**

本项目锁定使用 `crewai==1.14.4`，模型名使用 LiteLLM 的 `anthropic/` 前缀格式（如 `anthropic/claude-sonnet-4-5`），这是 CrewAI v1.x 的要求。如果你安装了其他版本，请严格按照 `requirements.txt` 安装：

```bash
pip install -r requirements.txt
```

---

**Q: 定制简历内容有遗漏或改动过大**

Rewrite Agent 的 Prompt 中明确要求「不虚构任何经历、技能或数据」，仅对已有内容进行重新表述和排序。如果发现明显问题，建议：

1. 检查原始简历是否粘贴完整
2. 检查 JD 是否包含足够详细的岗位要求
3. 将 `tailored_resume.md` 作为参考，手动微调关键细节后再使用

---

**Q: 如何更换 Agent 使用的模型**

在 `config.py` 中修改模型常量，使用 LiteLLM 支持的 Anthropic 模型 ID：

```python
# config.py
SONNET = "anthropic/claude-sonnet-4-5"   # 改为其他 Sonnet 模型
HAIKU  = "anthropic/claude-haiku-4-5-20251001"  # 改为其他 Haiku 模型
```

---

**Q: 如何扩展自定义工具（如联网搜索公司信息）**

`tools/` 目录是预留的扩展入口。参照 [CrewAI Tools 文档](https://docs.crewai.com/concepts/tools) 创建自定义 Tool，然后在对应 Agent 的 `make_*_agent()` 函数中通过 `tools=[your_tool]` 参数注入即可。
