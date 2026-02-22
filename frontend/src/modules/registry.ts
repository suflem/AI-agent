import type { UiModule } from "../types/ui";

export const allModules: UiModule[] = [
  {
    key: "study",
    title: "学习中心",
    summary: "知识检索、概念讲解与学习计划。",
    actions: [
      {
        id: "study-pack",
        name: "生成备考包",
        description: "基于主题生成聚焦备考内容。",
        path: "/study/pack",
        fields: [
          { key: "topic", label: "主题", type: "text", required: true, placeholder: "线性代数期末" },
          { key: "level", label: "难度等级", type: "text", placeholder: "本科" },
          { key: "days_left", label: "剩余天数", type: "number", min: 1, placeholder: "14" },
        ],
      },
      {
        id: "study-explain",
        name: "讲解概念",
        description: "按指定深度和受众讲解概念。",
        path: "/study/explain",
        fields: [
          { key: "concept", label: "概念", type: "text", required: true, placeholder: "反向传播" },
          { key: "audience", label: "受众", type: "text", placeholder: "大一学生" },
          { key: "depth", label: "讲解深度", type: "text", placeholder: "直觉 + 公式" },
        ],
      },
      {
        id: "study-plan",
        name: "学习计划",
        description: "生成基于时间线的学习安排。",
        path: "/study/plan",
        fields: [
          { key: "goal", label: "目标", type: "text", required: true, placeholder: "GRE Verbal 160+" },
          { key: "days", label: "总天数", type: "number", min: 1, placeholder: "30" },
          { key: "daily_hours", label: "每日学习时长", type: "number", min: 1, max: 16, placeholder: "3" },
        ],
      },
    ],
  },
  {
    key: "academic",
    title: "学术写作",
    summary: "撰写并润色学术文本。",
    actions: [
      {
        id: "academic-write",
        name: "生成初稿",
        description: "根据写作意图生成初稿。",
        path: "/academic/write",
        fields: [
          { key: "task", label: "任务", type: "text", required: true, placeholder: "CS 硕士申请 SOP" },
          { key: "tone", label: "语气风格", type: "text", placeholder: "专业、简洁" },
          { key: "constraints", label: "约束条件", type: "textarea", rows: 4, placeholder: "字数限制、章节结构..." },
        ],
      },
      {
        id: "academic-revise",
        name: "润色文本",
        description: "按明确要求修改已有草稿。",
        path: "/academic/revise",
        fields: [
          { key: "draft", label: "草稿内容", type: "textarea", rows: 8, required: true, placeholder: "粘贴草稿文本" },
          { key: "requirements", label: "修改要求", type: "textarea", rows: 5, placeholder: "语气、结构等" },
        ],
      },
    ],
  },
  {
    key: "grad",
    title: "升学决策",
    summary: "调研、对比、打分并规划申请路径。",
    actions: [
      {
        id: "grad-manage",
        name: "管理档案",
        description: "新增或更新申请者资料。",
        path: "/grad/manage",
        fields: [
          { key: "operation", label: "操作", type: "text", required: true, placeholder: "create|update|delete|get" },
          { key: "student_id", label: "学生 ID", type: "text", placeholder: "s_2026_001" },
          {
            key: "payload",
            label: "载荷 JSON",
            type: "json",
            rows: 6,
            placeholder: "{\"gpa\":3.8,\"major\":\"CS\"}",
          },
        ],
      },
      {
        id: "grad-research",
        name: "项目调研",
        description: "通过网络或知识库调研目标项目。",
        path: "/grad/research",
        fields: [
          { key: "target", label: "目标", type: "text", required: true, placeholder: "美国 NLP 硕士" },
          { key: "constraints", label: "约束条件", type: "textarea", rows: 4, placeholder: "预算、地区..." },
        ],
      },
      {
        id: "grad-compare",
        name: "候选对比",
        description: "使用加权标准比较候选学校。",
        path: "/grad/compare",
        fields: [
          { key: "candidates", label: "候选 JSON", type: "json", rows: 8, required: true, placeholder: "[{\"school\":\"A\"}]" },
          {
            key: "weights",
            label: "权重 JSON",
            type: "json",
            rows: 5,
            placeholder: "{\"cost\":0.2,\"rank\":0.4,\"fit\":0.4}",
          },
        ],
      },
      {
        id: "grad-scorecard",
        name: "生成评分卡",
        description: "按可配置维度评估人校匹配度。",
        path: "/grad/scorecard",
        fields: [
          { key: "profile", label: "档案 JSON", type: "json", rows: 6, required: true, placeholder: "{\"gpa\":3.7}" },
          { key: "programs", label: "项目 JSON", type: "json", rows: 8, required: true, placeholder: "[{\"name\":\"X\"}]" },
        ],
      },
      {
        id: "grad-timeline",
        name: "生成时间线",
        description: "生成里程碑与截止日期时间线。",
        path: "/grad/timeline",
        fields: [
          { key: "intake", label: "入学批次", type: "text", required: true, placeholder: "2027 秋季" },
          { key: "deadlines", label: "截止 JSON", type: "json", rows: 6, placeholder: "[{\"task\":\"TOEFL\",\"date\":\"2026-08-01\"}]" },
        ],
      },
    ],
  },
  {
    key: "feed",
    title: "信息流",
    summary: "采集并摘要外部信息源。",
    actions: [
      {
        id: "feed-rss",
        name: "导入 RSS",
        description: "拉取并解析 RSS 条目。",
        path: "/feed/rss",
        fields: [
          { key: "sources", label: "RSS 源 JSON", type: "json", rows: 6, required: true, placeholder: "[\"https://...\"]" },
          { key: "max_items", label: "最大条数", type: "number", min: 1, max: 200, placeholder: "50" },
        ],
      },
      {
        id: "feed-wechat",
        name: "接入微信公众号",
        description: "导入公众号信息流条目。",
        path: "/feed/wechat",
        fields: [
          { key: "accounts", label: "账号 JSON", type: "json", rows: 6, required: true, placeholder: "[\"account_id\"]" },
          { key: "keywords", label: "关键词", type: "text", placeholder: "LLM, scholarship" },
        ],
      },
      {
        id: "feed-pipeline",
        name: "执行流水线",
        description: "标准化并任务化原始信息流。",
        path: "/feed/pipeline",
        fields: [
          { key: "items", label: "条目 JSON", type: "json", rows: 8, required: true, placeholder: "[{\"title\":\"...\"}]" },
        ],
      },
      {
        id: "feed-digest",
        name: "生成摘要",
        description: "从当前信息批次生成简报。",
        path: "/feed/digest",
        fields: [
          { key: "records", label: "记录 JSON", type: "json", rows: 8, required: true, placeholder: "[{\"summary\":\"...\"}]" },
          { key: "style", label: "风格", type: "text", placeholder: "简要要点" },
        ],
      },
    ],
  },
  {
    key: "memory",
    title: "记忆中心",
    summary: "会话记忆、主题记忆与向量记忆操作。",
    actions: [
      {
        id: "memory-save-global",
        name: "保存全局记忆",
        description: "将稳定偏好写入全局记忆（需审批）。",
        path: "/tool/call?tool=save_memory",
        fields: [
          {
            key: "content",
            label: "内容",
            type: "textarea",
            rows: 5,
            required: true,
            placeholder: "用户偏好中文且回答简洁。",
          },
          { key: "is_global", label: "全局", type: "boolean", defaultValue: true },
        ],
      },
      {
        id: "memory-save-topic",
        name: "保存主题记忆",
        description: "将主题记忆写入 memories/<topic>.txt（需审批）。",
        path: "/tool/call?tool=save_memory",
        fields: [
          {
            key: "content",
            label: "内容",
            type: "textarea",
            rows: 5,
            required: true,
            placeholder: "项目约束与上下文快照...",
          },
          { key: "is_global", label: "全局", type: "boolean", defaultValue: false },
          { key: "topic_name", label: "主题名", type: "text", required: true, placeholder: "project_alpha" },
        ],
      },
      {
        id: "memory-read-topic",
        name: "读取主题记忆",
        description: "按主题名读取记忆。",
        path: "/tool/call?tool=read_memory",
        fields: [{ key: "topic_name", label: "主题名", type: "text", required: true, placeholder: "project_alpha" }],
      },
      {
        id: "memory-list",
        name: "列出主题",
        description: "列出所有已保存的主题记忆。",
        path: "/tool/call?tool=list_memories",
        fields: [],
      },
      {
        id: "memory-rag-save",
        name: "保存向量记忆",
        description: "将语义记忆写入 ChromaDB。",
        path: "/tool/call?tool=rag_save",
        fields: [
          {
            key: "content",
            label: "内容",
            type: "textarea",
            rows: 6,
            required: true,
            placeholder: "需要嵌入的长文本笔记或偏好...",
          },
          { key: "tags", label: "标签", type: "text", placeholder: "study,projectA,preference" },
        ],
      },
      {
        id: "memory-rag-search",
        name: "检索向量记忆",
        description: "在向量记忆库中进行语义检索。",
        path: "/tool/call?tool=rag_search",
        fields: [
          { key: "query", label: "查询", type: "text", required: true, placeholder: "我的 SOP 写作约束是什么？" },
          { key: "top_k", label: "返回数量 Top K", type: "number", min: 1, max: 20, placeholder: "5" },
        ],
      },
      {
        id: "memory-rag-status",
        name: "向量记忆状态",
        description: "查看向量索引大小与位置。",
        path: "/tool/call?tool=rag_status",
        fields: [],
      },
      {
        id: "memory-last-chat",
        name: "读取最近会话记录",
        description: "读取最近持久化的 CLI 会话历史文件。",
        path: "/tool/call?tool=read_file",
        fields: [
          {
            key: "filename",
            label: "文件名",
            type: "text",
            required: true,
            defaultValue: "memories/chat_history/latest.json",
            placeholder: "memories/chat_history/latest.json",
          },
        ],
      },
    ],
  },
  {
    key: "skill_studio",
    title: "技能工坊",
    summary: "可视化技能脚手架创建，支持后端 AI 辅助补全。",
    actions: [
      {
        id: "skill-preview",
        name: "预览技能脚手架",
        description: "在不写入文件的情况下生成标准化脚手架预览。",
        path: "/tool/call?tool=skill_scaffold_preview",
        fields: [
          { key: "module_name", label: "模块名", type: "text", required: true, placeholder: "custom_tools" },
          { key: "tool_name", label: "工具名", type: "text", required: true, placeholder: "custom_lookup" },
          {
            key: "description",
            label: "描述",
            type: "textarea",
            rows: 4,
            required: true,
            placeholder: "查询并规范化自定义业务记录。",
          },
          {
            key: "params",
            label: "参数 JSON",
            type: "json",
            rows: 10,
            required: true,
            defaultValue:
              "[\n  {\"name\":\"query\",\"type\":\"string\",\"description\":\"search text\",\"required\":true},\n  {\"name\":\"top_k\",\"type\":\"integer\",\"description\":\"max results\",\"required\":false,\"default\":5}\n]",
            placeholder:
              "[{\"name\":\"query\",\"type\":\"string\",\"description\":\"search text\",\"required\":true}]",
          },
          { key: "use_ai_completion", label: "AI 补全", type: "boolean", defaultValue: true },
          {
            key: "implementation_hint",
            label: "实现提示",
            type: "textarea",
            rows: 3,
            placeholder: "先返回确定性的 mock 数据，再给总结。",
          },
        ],
      },
      {
        id: "skill-create",
        name: "创建技能文件",
        description: "写入技能脚手架文件，并可选自动注册导入/风险控制。",
        path: "/tool/call?tool=skill_scaffold_create",
        fields: [
          { key: "module_name", label: "模块名", type: "text", required: true, placeholder: "custom_tools" },
          { key: "tool_name", label: "工具名", type: "text", required: true, placeholder: "custom_lookup" },
          {
            key: "description",
            label: "描述",
            type: "textarea",
            rows: 4,
            required: true,
            placeholder: "查询并规范化自定义业务记录。",
          },
          {
            key: "params",
            label: "参数 JSON",
            type: "json",
            rows: 10,
            required: true,
            defaultValue:
              "[\n  {\"name\":\"query\",\"type\":\"string\",\"description\":\"search text\",\"required\":true},\n  {\"name\":\"top_k\",\"type\":\"integer\",\"description\":\"max results\",\"required\":false,\"default\":5}\n]",
            placeholder:
              "[{\"name\":\"query\",\"type\":\"string\",\"description\":\"search text\",\"required\":true}]",
          },
          { key: "use_ai_completion", label: "AI 补全", type: "boolean", defaultValue: true },
          {
            key: "implementation_hint",
            label: "实现提示",
            type: "textarea",
            rows: 3,
            placeholder: "先返回确定性的 mock 数据，再给总结。",
          },
          { key: "auto_register_import", label: "自动注册导入", type: "boolean", defaultValue: true },
          { key: "mark_risky", label: "标记高风险", type: "boolean", defaultValue: false },
          { key: "overwrite", label: "覆盖已存在文件", type: "boolean", defaultValue: false },
        ],
      },
    ],
  },
  {
    key: "daily_notify",
    title: "计划与通知",
    summary: "待办、提醒、通知和调度任务操作。",
    actions: [
      {
        id: "daily-todo",
        name: "管理待办",
        description: "创建或更新待办事项。",
        path: "/daily/todo",
        fields: [
          { key: "operation", label: "操作", type: "text", required: true, placeholder: "create|update|done|list" },
          { key: "title", label: "标题", type: "text", placeholder: "准备推荐材料" },
          { key: "due_at", label: "截止时间", type: "text", placeholder: "2026-02-20T18:00:00" },
        ],
      },
      {
        id: "daily-reminder",
        name: "设置提醒",
        description: "创建提醒项。",
        path: "/daily/reminder",
        fields: [
          { key: "message", label: "提醒内容", type: "text", required: true, placeholder: "提交奖学金申请表" },
          { key: "trigger_at", label: "触发时间", type: "text", placeholder: "2026-02-18T09:00:00" },
        ],
      },
      {
        id: "notify-send",
        name: "发送通知",
        description: "向指定渠道发送一次性通知。",
        path: "/notify/send",
        fields: [
          { key: "channel", label: "渠道", type: "text", required: true, placeholder: "email|telegram|wechat" },
          { key: "content", label: "内容", type: "textarea", rows: 5, required: true, placeholder: "通知内容" },
        ],
      },
      {
        id: "scheduler-run",
        name: "执行任务",
        description: "手动触发调度任务。",
        path: "/scheduler/run",
        fields: [
          { key: "job_id", label: "任务 ID", type: "text", required: true, placeholder: "daily_digest_job" },
          { key: "force", label: "强制执行", type: "boolean", defaultValue: false },
        ],
      },
      {
        id: "scheduler-log",
        name: "获取日志",
        description: "获取调度执行日志。",
        path: "/scheduler/log",
        fields: [{ key: "limit", label: "条数限制", type: "number", min: 1, max: 200, placeholder: "20" }],
      },
    ],
  },
];

export const moduleByKey = Object.fromEntries(allModules.map((m) => [m.key, m])) as Partial<Record<string, UiModule>>;
