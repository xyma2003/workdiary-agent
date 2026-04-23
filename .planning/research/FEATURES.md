# Feature Landscape

**Domain:** AI Writing Assistant — Daily Work Report Generator (智能日报 Agent)
**Researched:** 2026-04-22
**Confidence note:** Web search returned no results. All findings are from training knowledge (cutoff Aug 2025) + domain analysis. Confidence levels marked per claim.

---

## Table Stakes

Features users expect from any AI report-writing tool. Missing = product feels incomplete or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Natural-language input | Core promise — "just describe your day" | Low | Must accept unstructured, typo-laden, Chinglish input |
| Structured output with clear sections | Managers scan, not read — no structure = not usable | Low | See "Template Sections" below |
| One-click regenerate | AI output is never perfect first time — users need escape hatch | Low | Simplest form of human-in-the-loop |
| Editable output before export | Users must trust they control the final text | Low | Inline edit in Streamlit text_area |
| Copy-to-clipboard | Final destination is WeChat / DingTalk / Feishu — must be pasteable | Low | st.code block or custom copy button |
| Markdown export | Professional artifact, version-controllable | Low | Already in scope (FILE write) |
| Input → output in < 10 seconds | Slow generation kills the "5-minute daily report" promise | Medium | Streaming response helps perception |
| History / recall | "What did I write last Tuesday?" is a daily need | Medium | Already in scope (SQLite) |
| Business-value framing in output | Core differentiator of "老板视角" — if absent, tool is just a grammar fixer | High (prompt) | The hardest part is the prompt engineering |

**Confidence:** HIGH for structural expectations; MEDIUM for timing expectations (subjective).

---

## Template Sections — What a Good Daily Report Contains

Based on established Chinese workplace reporting conventions and what managers prioritize. These sections map directly to what TemplateRouterAgent needs to populate.

### Universal Sections (all three template types)

| Section | Chinese Label | What Goes Here | Boss Priority |
|---------|---------------|----------------|---------------|
| Today's completed work | 今日完成 | Concrete deliverables, not activities | HIGHEST — leads the report |
| Progress against plan | 完成情况/进度 | % complete, milestone hit/miss | HIGH |
| Key metrics / quantification | 量化指标 | Numbers: PRs merged, tests passed, conversion +X%, calls made | HIGH |
| Blockers / risks | 风险/问题 | What's blocking, what help is needed | HIGH — managers need to unblock |
| Tomorrow's plan | 明日计划 | Concrete next steps, not vague intentions | MEDIUM |
| Context notes (optional) | 备注/说明 | One-liner context that explains anything unusual | LOW |

### Template Type Differences

**Technical template (技术型)** — for engineers, data roles:
- Sections: Completed tasks (with PR/commit refs if available) → Technical blockers → Code metrics → Tomorrow's technical plan
- Tone: Precise, outcome-focused, avoids "worked on X" in favor of "shipped X"
- Quantification: PRs, tests, performance numbers, bug counts

**Business template (业务型)** — for sales, operations, BD, PM:
- Sections: Key business activities → Outcomes achieved → Client / stakeholder status → Risks → Next actions
- Tone: Value and impact language, relationship-aware
- Quantification: Revenue, conversion, GMV, call count, deal stage

**Hybrid template (混合型)** — for tech PMs, full-stack team leads:
- Combines technical delivery + business outcome per item
- Maps each technical output to a business impact: "Shipped feature X → enables Y use case → unblocks Q3 target"

---

## "Boss-Friendly" Writing Principles

What distinguishes output that managers appreciate from generic summaries. HIGH confidence — these are well-established management communication patterns.

### 1. Lead with outcomes, not activities

Bad: "今天开了三个会，讨论了需求"
Good: "完成需求评审，核心功能范围达成一致，下周可进入开发阶段"

### 2. Quantify everything quantifiable

The agent should actively hunt for numbers in casual input. Heuristics:
- Time saved → "减少X小时人工操作"
- Count → "处理了X条case"
- Rate → "通过率从X%提升至Y%"
- Stage → "推进至X阶段"
- If no number exists → use relative scale ("完成首版" / "初步验证可行性")

### 3. Surface blockers explicitly with ownership

Bad: "有些问题还没解决"
Good: "【待确认】数据库权限问题阻塞测试，需运维团队配合，预计影响1天"

### 4. Forward-looking close

Every report ends with tomorrow's top 2-3 priorities. This signals manager that reporter is proactive, not reactive.

### 5. Appropriate formality level

Chinese workplace reports use a semi-formal register:
- No slang (不用"搞定了""怼了一下")
- Concrete verbs: 完成/推进/对齐/确认/输出/跟进
- Avoid passive constructions where possible

### 6. Length discipline

Managers prefer 150-300 characters per section, not walls of text. The agent should compress, not expand.

---

## Differentiators

Features that set this tool apart from generic AI writing tools or simple prompt wrappers. These are what makes the portfolio project interesting.

| Feature | Value Proposition | Complexity | Interview Signal |
|---------|-------------------|------------|-----------------|
| TemplateRouterAgent — auto-detect report type | User doesn't choose template manually; agent infers from content | Medium (classification prompt) | Shows multi-agent routing thinking |
| Git log as context tool | Concrete work evidence grounding the report — not just LLM hallucination | Medium (file I/O + tool call) | Shows tool-use / Agent-as-reasoner |
| Targeted regeneration ("just fix the metrics section") | User points at a specific section for revision, not full redo | Medium (state-scoped edit) | Shows human-in-the-loop sophistication |
| Confidence scoring per section | Agent flags sections where it had to infer heavily (low evidence) | High (self-evaluation prompt) | Shows meta-cognition, useful for demos |
| Writing style memory (personal style adaptation) | After N reports, agent adapts to user's habitual phrasing | High (embedding + retrieval) | Out of scope for v1 |
| Diff view before/after | Shows user exactly what the agent changed vs raw input | Low (Streamlit) | Good demo artifact for portfolio |
| Quantification prompting | When agent detects vague input ("开了几个会"), it asks for the number before drafting | Medium (conditional node) | Shows agentic judgment vs passive generation |

---

## Human-in-the-Loop (HITL) Patterns

For AI writing tools, HITL is not optional — it is the core trust mechanism. These are the patterns used in production AI writing tools (Notion AI, GitHub Copilot, Jasper, etc.) and LangGraph's own HITL design.

**Confidence:** MEDIUM-HIGH based on training knowledge of LangGraph interrupt pattern and general AI writing tool UX.

### Pattern 1: Interrupt-and-confirm (what the project uses)

Flow: Agent generates draft → PAUSE → User reviews → User chooses: Accept / Reject / Edit request → Agent continues or reruns

LangGraph implementation: `interrupt()` at the human review node. State checkpoint preserves the draft. User submits feedback via Streamlit form. Graph resumes from checkpoint.

Key UX considerations:
- Show the draft prominently before asking for feedback
- Give user 3 clear choices: Accept / Regenerate / Give specific feedback
- Specific feedback input must be free text (user knows what's wrong better than any dropdown)

### Pattern 2: Retry with max limit

Pattern: If user rejects, agent reruns with rejection context appended to prompt. Cap at N attempts (project has this: `low_confidence_count`).

Why the cap matters: Infinite loops kill UX. After 3 failed attempts, surface the raw draft with a "manual edit" fallback. Never leave user stuck.

State to carry across retries:
- Original raw input
- All previous drafts
- All rejection reasons (accumulate — each retry uses full history)
- Retry count

### Pattern 3: Section-level targeted edit (differentiator)

Instead of full regeneration, user selects which section needs fixing and provides targeted instruction. Agent only rewrites that section, keeping others frozen.

Implementation: Streamlit expanders per section + per-section feedback textarea. Node receives `{section: "blockers", instruction: "add who owns the blocker"}`.

### Pattern 4: Accept-with-edit (most common actual user behavior)

User accepts the draft but makes small manual edits directly in the text area before exporting. This is NOT the agent editing — it's direct user editing.

Implementation: Streamlit `st.text_area` showing draft. User edits inline. Export uses whatever is in the text_area at export time, not the original agent output.

This is the most-used path in practice. Tools that force agent-only editing (no direct edit) frustrate users.

---

## Anti-Features (Deliberately NOT Building)

Features to explicitly exclude from v1, with rationale. These align with the PROJECT.md Out of Scope section but add new items based on domain research.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Send to Feishu / DingTalk / WeChat Work | External API auth complexity (OAuth, webhook), testing burden, out of scope for one-week build | Export markdown + user pastes manually |
| Custom template editor | Template schema is complex UI; 3 preset templates cover 90% of cases | Hard-code 3 templates, document extension path in README |
| Multi-user / auth | Adds auth layer, session management, database per-user isolation — not a portfolio differentiator | Single user, local-only |
| Report "send schedule" / reminders | Scheduling infrastructure (cron, background worker) — wrong scope | Out of scope |
| Voice input | Good UX idea but adds speech-to-text dependency, latency, error handling — doubles complexity | Text-only v1; easy to add later |
| Automatic report categorization history with search | Full-text search over SQLite history is medium complexity but adds UI surface | Simple date-sorted history list |
| Tone/style selector UI (formal vs casual) | Three template types already encode different tones — a separate tone slider is redundant controls | Bake tone into template routing decision |
| Streaming token-by-token display | Nice UX but adds state complexity with LangGraph checkpointing — streaming state not trivial to reconcile | Show spinner + full result when complete (simpler, still fast enough) |
| Report scoring / grading | "Your report scores 8/10" — feels gamified and patronizing in a workplace tool | Silent quality improvement via prompt engineering |
| Plugin system / extensibility API | Over-engineering for a one-week portfolio project | Clean code structure is the extensibility signal |

---

## Feature Dependencies

```
Raw input parsing
  └── Template type detection (TemplateRouterAgent)
        └── Draft generation (per-template prompt)
              └── Human review node (interrupt)
                    ├── Accept path → export + SQLite save
                    ├── Reject/revise path → regenerate loop (max N)
                    │     └── Accumulate rejection context → re-draft
                    └── Section-targeted edit (optional, differentiator)
                          └── Partial re-draft for specified section only

Git log tool (optional, parallel to raw input)
  └── Feeds additional context into draft generation node
  └── Does NOT gate the main flow (graceful degradation if no git repo)
```

Dependency constraints:
- TemplateRouterAgent must run BEFORE draft generation (template determines prompt)
- Human review node requires a complete draft (cannot interrupt mid-generation)
- SQLite save must happen AFTER user final accept (not on first draft)
- Git log is optional — main flow must work without it (test without git first)

---

## MVP Feature Prioritization

### Must have (MVP — week one)

1. Natural-language input → structured extraction → template-routed draft generation
2. Three templates (technical / business / hybrid) with boss-friendly prompt engineering
3. Human review interrupt: Accept / Reject-with-feedback / Direct edit
4. Retry loop with max 3 retries, accumulating feedback context
5. Markdown export to file
6. SQLite history (write + simple date-based read)
7. Streamlit UI covering full flow

### Should have (MVP stretch — if time allows)

8. Git log optional context tool (adds "real agent" signal for portfolio)
9. Diff view showing what changed between raw input and polished output (low complexity, high demo value)
10. Section-targeted feedback (medium complexity — worth doing if git log is done early)

### Defer post-v1

11. Confidence scoring per section (self-evaluation prompt adds latency + complexity)
12. Style memory / personalization (requires embedding + retrieval layer)
13. Voice input
14. Any external integrations (Feishu, DingTalk, etc.)

---

## Sources

All findings based on training knowledge (cutoff Aug 2025). No web search results were returned during this research session. Confidence levels:

- Template sections and boss-friendly writing principles: HIGH — well-established Chinese workplace communication conventions, cross-validated against PROJECT.md requirements
- Human-in-the-loop patterns: HIGH — LangGraph HITL interrupt pattern is a core documented feature; AI writing tool UX patterns are well-established
- Anti-features list: HIGH — based on PROJECT.md Out of Scope decisions + general scope-control principles for one-week builds
- Differentiator features: MEDIUM — based on analysis of what makes a "prompt wrapper" vs a real agent; interview value claims are judgment calls
- Timing expectations (< 10 second generation): MEDIUM — subjective UX threshold, not from empirical study
