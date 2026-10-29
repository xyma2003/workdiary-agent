# Evidence, review and local storage

[Back to the project](../README.md) · [Configuration](configuration.md)

Deleting a saved report removes its history row first and attempts to clean up its
managed Markdown export. If cleanup fails, the page shows a partial-success
warning and a **待清理导出 → 重试清理** action. Pending tasks are stored in
`history.db`, so they remain available after a refresh or restart, even when no
reports remain. Missing files count as already cleaned up. Files outside the export
directory, paths containing symlinks, and exports still used by another report are
preserved with an explicit notice.

### Editing from more than one page

History edits remember the version that was opened. If another page saves a
change first, the older editor shows a conflict and keeps its unsaved text.
Copy any text you need, cancel the edit, and reopen the latest version before
saving again. Edits serialize the database update and Markdown export so two
overlapping saves do not leave different report contents in those two places.
This handles competing edits and recoverable write errors; it is not an atomic
transaction across SQLite and the filesystem during a process or machine crash.
If SQLite automatically rolls back and another save or deletion has already
taken over, the failed edit skips its old file restoration. This protects the
newer result; an unused export created by the failed edit may remain for manual
inspection. That error path does not yet queue an automatic cleanup task.

### Privacy and trust boundaries

- Work notes, pasted metrics, and selected Git commit subjects are sent to the configured LLM provider. Common credential formats are redacted in new source snapshots and before model calls, but this is best-effort; do not submit data your provider is not allowed to process. History and unfinished checkpoints are local files and may contain sensitive work material, including earlier inputs or subsequent edits.
- Git enrichment skips commit collection when it cannot resolve an explicit author/email or `user.email` / `user.name` from the repository’s effective Git configuration (including inherited settings); it never attributes every contributor's commits to you.
- User text and repository-derived text are delimited as untrusted source data in prompts. This reduces prompt-injection risk but is not a complete security boundary.
- Repository paths are read from the machine running Streamlit. Keep the app local or add deployment-level access controls before exposing it to other users.

### Review against the original material

Before accepting a report, **原始材料** and **待审日报** appear side by side.
The source panel shows the frozen work description, pasted metric text and Git
commit subjects; long sources scroll independently. You can edit the report,
request a revision or download the current text while checking those sources.
The new-report form is collapsed during review so the active report stays in view.

**模型提炼的指标摘要（非原始证据）** is a separate, labeled section. Fact warnings
use the same frozen original sources shown in the panel, not the model's summary
or changes to the new-report form. These checks flag possible issues; they do not
prove factual correctness. A new report edit resets any warning acknowledgement.
When resuming an older task without a source snapshot, the app labels its remaining
checkpoint material as incomplete instead of reading today's repository.

Time-unit checks flag a supported number/unit pair when the same numeric value
appears in the frozen sources with other time units, but not with the report's
unit: for example, **10 ms → 10 s**. The warning uses the existing review flow:
correct the report, or explicitly acknowledge it after checking the sources.
Editing the report invalidates that acknowledgement.

The check recognizes unsigned ASCII integers and decimals with a leading digit
(including grouped commas), with these case-insensitive English or Chinese units:

| Unit | Accepted forms |
| --- | --- |
| Milliseconds | `ms`, `millisecond(s)`, `毫秒` |
| Seconds | `s`, `sec(s)`, `second(s)`, `秒` |
| Minutes | `min(s)`, `minute(s)`, `分钟` |
| Hours | `h`, `hr(s)`, `hour(s)`, `小时` |
| Days | `d`, `day(s)`, `天` |

Trailing decimal zeros and leading integer zeros do not change the compared
value. This is a conservative warning: it does not match values to specific
metrics or assess conversions such as **1000 ms → 1 s**. The original number
checks still apply independently. Ambiguous shorthand (`m`, `分`, `时`, `日`),
signed values, scientific notation, compound units, and other quantities are not
validated by this check. A matching pair anywhere in the original material suppresses this
unit warning, so it is not evidence that the report's claim is correct.

### Inspect a saved report's sources

In **历史记录**, expand **生成时的来源快照** to compare the original material with
the currently saved report. You can inspect the work description and raw pasted
metrics used for generation, the selected Git commit subjects, and the resolved
author/date/timezone filters. The snapshot is checkpointed before
the first model stage: later Git changes or a retry after a model failure do not
silently replace those sources. A missing/unavailable Git result is recorded as
such; the snapshot is not a backup of repository files or the entire commit history.

The same view shows provider/model configuration for clients created in each
successfully completed generation stage, including both router calls and later
revision passes. It does not claim the provider actually served a particular
model revision, or record every failed request/retry. API keys and request headers
are excluded; endpoint identifiers retain only the origin, without user info,
paths, queries or fragments. Model-derived metric summaries are not presented as
raw evidence.

The snapshot is stored once alongside the approved report in `history.db`.
Editing the report, its date or its editable input preserves that original
snapshot. Markdown exports continue to contain only the report. Older reports
and tasks without capture data show **来源未保存**; the app never reconstructs
their historical evidence from the current environment or repository. Unreadable
or unsupported snapshots show a notice while the report remains usable.
