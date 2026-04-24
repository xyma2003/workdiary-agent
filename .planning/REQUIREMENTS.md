# Requirements: 智能日报 Agent (WorkDiary Agent)

**Defined:** 2026-04-23
**Core Value:** 用户输入一段口语化的工作描述，Agent 能自动生成一份老板视角的专业日报，让用户5分钟内完成每日汇报。

## v1 Requirements

### Agent 核心流程 (AGENT)

- [x] **AGENT-01**: 用户可以用自然语言（口语化）在输入框中描述今天的工作内容
- [x] **AGENT-02**: 系统从用户输入中提取结构化信息（任务、产出、遇到的问题、推进进度）
- [x] **AGENT-03**: 用户可选填写本地 Git repo 路径，系统自动读取今日 commits 作为辅助上下文
- [x] **AGENT-04**: 系统可解析用户粘贴的数字/指标、表格文本或上传的 CSV 文件，提取数据特征并融入日报（数据输入为可选项）
- [x] **AGENT-05**: TemplateRouterAgent 根据提取的内容自动判断日报类型（技术型/业务型/混合型）
- [x] **AGENT-06**: 系统按选定模板生成日报初稿
- [x] **AGENT-07**: 系统以老板视角对初稿进行润色改写（突出业务价值、量化指标、用"完成/推进/对齐/输出/跟进"等动词）

### 人工确认与修改 (HITL)

- [x] **HITL-01**: 生成初稿后系统暂停，用户可查看完整日报内容
- [x] **HITL-02**: 用户可直接在文本框中编辑日报内容（inline 编辑，accept-with-edit 路径）
- [x] **HITL-03**: 用户可输入修改意见，Agent 根据反馈重新润色（最多循环3次）
- [x] **HITL-04**: 用户可一键接受当前版本，结束生成流程

### 模板系统 (TMPL)

- [x] **TMPL-01**: 系统内置3种日报模板：技术型（突出方案/进度）、业务型（突出数据/结论/下一步）、混合型（技术产出关联业务影响）
- [x] **TMPL-02**: TemplateRouterAgent 的路由决策对用户可见（显示"已选用XX模板"）
- [x] **TMPL-03**: 用户可手动覆盖自动选择的模板类型

### 存储与导出 (STORE)

- [x] **STORE-01**: 每次生成的最终日报自动保存到 SQLite 历史库（含日期、模板类型、原始输入、最终输出）
- [x] **STORE-02**: 用户可在界面中查看历史日报列表（按日期排序）
- [x] **STORE-03**: 用户可一键将当前日报导出为 markdown 文件（文件名含日期）

### UI 界面 (UI)

- [x] **UI-01**: Streamlit 界面包含输入区（工作描述、可选 Git 路径、可选数据粘贴/上传）
- [x] **UI-02**: 界面展示 Agent 当前处理节点状态（如"正在提取信息…"/"正在润色…"）
- [x] **UI-03**: 界面展示生成的日报内容，支持直接编辑
- [x] **UI-04**: 界面提供"接受"/"重新生成（附反馈）"/"导出"操作按钮
- [x] **UI-05**: 界面提供历史日报查看入口

## v2 Requirements

### 增强功能

- **ENH-01**: 用户可自定义/编辑日报模板
- **ENH-02**: 一键发送到飞书/钉钉 Webhook
- **ENH-03**: 历史日报全文搜索
- **ENH-04**: 周报自动汇总（聚合一周日报生成周报）
- **ENH-05**: 流式输出（streaming），实时展示生成过程

## Out of Scope

| Feature | Reason |
|---------|--------|
| 自动发送飞书/钉钉 | 外部 API 依赖，一周内时间不够，用户可手动复制 |
| 多用户/账号系统 | 个人工具，单用户场景 |
| 移动端适配 | Streamlit 桌面端已足够 |
| 用户自定义模板编辑器 | v2 功能，v1 预设3种已够展示 |
| 流式输出 | 增加 Streamlit+LangGraph 集成复杂度，v2 再加 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AGENT-01 | Phase 1 | Complete |
| AGENT-02 | Phase 2 | Complete |
| AGENT-03 | Phase 3 | Complete |
| AGENT-04 | Phase 3 | Complete |
| AGENT-05 | Phase 2 | Complete |
| AGENT-06 | Phase 2 | Complete |
| AGENT-07 | Phase 2 | Complete |
| HITL-01 | Phase 4 | Complete |
| HITL-02 | Phase 4 | Complete |
| HITL-03 | Phase 4 | Complete |
| HITL-04 | Phase 4 | Complete |
| TMPL-01 | Phase 2 | Complete |
| TMPL-02 | Phase 2 | Complete |
| TMPL-03 | Phase 2 | Complete |
| STORE-01 | Phase 5 | Complete |
| STORE-02 | Phase 5 | Complete |
| STORE-03 | Phase 5 | Complete |
| UI-01 | Phase 6 | Complete |
| UI-02 | Phase 6 | Complete |
| UI-03 | Phase 6 | Complete |
| UI-04 | Phase 6 | Complete |
| UI-05 | Phase 6 | Complete |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-04-23*
*Last updated: 2026-04-22 after roadmap creation*
