# API Contract (Frontend Integration)

Base URL: `http://127.0.0.1:8000`

## 1) System
- `GET /api/system/health?level=quick|full`
- `POST /api/system/smoke`

## 2) Generic Tool Gateway
- `GET /api/tool/list`
- `POST /api/tool/call?tool=<tool_name>`

Examples used by new UI modules:
- Memory:
  - `POST /api/tool/call?tool=save_memory`
  - `POST /api/tool/call?tool=read_memory`
  - `POST /api/tool/call?tool=list_memories`
  - `POST /api/tool/call?tool=rag_save`
  - `POST /api/tool/call?tool=rag_search`
  - `POST /api/tool/call?tool=rag_status`
- Skill Studio:
  - `POST /api/tool/call?tool=skill_scaffold_preview`
  - `POST /api/tool/call?tool=skill_scaffold_create`

## 3) Domain Endpoints
- Study:
  - `POST /api/study/pack`
  - `POST /api/study/explain`
  - `POST /api/study/plan`
- Academic:
  - `POST /api/academic/write`
  - `POST /api/academic/revise`
- Grad:
  - `POST /api/grad/manage`
  - `POST /api/grad/research`
  - `POST /api/grad/compare`
  - `POST /api/grad/scorecard`
  - `POST /api/grad/timeline`
- Feed:
  - `POST /api/feed/rss`
  - `POST /api/feed/wechat`
  - `POST /api/feed/pipeline`
  - `POST /api/feed/digest`
- Daily:
  - `POST /api/daily/todo`
  - `POST /api/daily/note`
  - `POST /api/daily/reminder`
- Notify:
  - `POST /api/notify/manage`
  - `POST /api/notify/send`
  - `POST /api/notify/reminder-push`
- Scheduler:
  - `POST /api/scheduler/manage`
  - `POST /api/scheduler/run`
  - `POST /api/scheduler/tick`
  - `POST /api/scheduler/log`
- Knowledge Base:
  - `POST /api/kb/build`
  - `POST /api/kb/query`
  - `POST /api/kb/manage`

## 4) Request Body (all POST endpoints except tool/list)

```json
{
  "args": {},
  "approval": {
    "dry_run": false,
    "confirm": false,
    "approval_id": "",
    "actor": "ui"
  }
}
```

## 5) Risky Tool Approval Flow
1. Send with `approval.dry_run=true`.
2. If response `status=needs_approval`, show `preview` to user.
3. Re-send same endpoint+args with:
   - `approval.confirm=true`
   - `approval.approval_id=<returned id>`
