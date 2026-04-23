# Phase 1: Graph Skeleton - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 01-graph-skeleton
**Areas discussed:** 目录结构, AgentState 字段设计, TemplateRouterAgent 接入方式, Checkpointer

---

## 目录结构

| Option | Description | Selected |
|--------|-------------|----------|
| 新建 workdiary_agent/ 目录 | 在项目根下新建包，与 桌面动物园/ 并列，目录边界清晰 | ✓ |
| 放在项目根目录 | graph.py、state.py 等直接放根，无包层 | |

**User's choice:** 新建 workdiary_agent/ 目录

| Option | Description | Selected |
|--------|-------------|----------|
| 层次化拆分（推荐） | graph.py + state.py + nodes/ + services/ + utils/ | ✓ |
| 单文件先跑通再拆 | Phase 1 全写在 graph.py 一个文件，后续再拆分 | |

**User's choice:** 层次化拆分

---

## AgentState 字段设计

| Option | Description | Selected |
|--------|-------------|----------|
| Pydantic BaseModel（推荐） | structured_info: Optional[StructuredInfo]，Phase 2 用 with_structured_output 填充 | ✓ |
| dict | structured_info: Optional[dict]，Phase 2 手动解析 JSON | |

**User's choice:** Pydantic BaseModel

| Option | Description | Selected |
|--------|-------------|----------|
| Literal["approve", "revise", "edit"] \| None（推荐） | 编译期类型检查，捕获错误输入 | ✓ |
| str \| None | 简单，运行时手动判断 | |

**User's choice:** Literal["approve", "revise", "edit"] | None

---

## TemplateRouterAgent 接入方式

| Option | Description | Selected |
|--------|-------------|----------|
| 普通 stub 函数，Phase 2 再改成子图（推荐） | Phase 1 route_template 是普通函数，最小化复杂度 | ✓ |
| 现在就展开成子图骨架 | Phase 1 就建好子图接口，Phase 2 填充内容 | |

**User's choice:** 普通 stub 函数，Phase 2 再改成子图

---

## Checkpointer

| Option | Description | Selected |
|--------|-------------|----------|
| 现在就用 MemorySaver（推荐） | compile(checkpointer=MemorySaver())，Phase 4 只换 SqliteSaver | ✓ |
| Phase 1 先不用 checkpointer | compile() 无参数，Phase 4 再加，但届时所有调用处都要改 config | |

**User's choice:** 现在就用 MemorySaver

---

## Claude's Discretion

- 各 stub 节点的具体返回内容（只要类型正确）
- nodes/ 子目录内的文件命名规范
- `__init__.py` 的导出方式

## Deferred Ideas

无
