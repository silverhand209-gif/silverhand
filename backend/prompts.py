"""集中式 Prompt 模板管理 — 3 Agent 串行架构"""

# ============================================================
# 公共 JSON 输出约束
# ============================================================
JSON_OUTPUT_RULES = """## JSON 输出规范（必须严格遵守）
- 输出纯 JSON，不要用 ```json 代码块包裹
- 所有字符串必须用双引号，不能用单引号
- 字符串内的换行符必须转义为 \\n，双引号转义为 \\"
- 对象的最后一个属性后面不能加逗号
- 所有属性名必须用双引号包裹
- null 必须小写"""

# ============================================================
# 0. 单章解构 Prompt — 逐章处理，支持无限章节扩展
# ============================================================
CHAPTER_DECONSTRUCT_PROMPT = """你是一位严谨的文学分析师。任务：仅解构本章内容，提取所有结构化元素。

## ⚠️ 对话提取（最重要）
- 逐句找到本章中**每一句**用引号包裹的人物对白，**每句一个独立条目**
- 包括：直接引号对话、转述对话、自言自语、人群喊话嘲讽议论
- **绝对禁止**：把多句对话合并。本章有30句对话就必须有30个条目
- 每个条目只需 speaker 和 line

## 当前章节信息
- 章节号：{chapter_number}
- 章节标题：{chapter_title}

## 本章原文
{chapter_text}

{json_rules}

## 输出 JSON Schema（仅本章数据）
{{
  "chapter_number": {chapter_number},
  "chapter_title": "章节标题",
  "summary": "本章情节摘要（100-300字）",
  "key_events": ["按顺序列出关键事件"],
  "new_characters": [
    {{
      "name": "角色名",
      "aliases": ["其他称呼"],
      "role_type": "protagonist/antagonist/supporting/minor",
      "personality": ["本章体现的性格"],
      "background": "背景信息",
      "dialogue_style": "说话风格",
      "dialogue_samples": ["本章真实对白"]
    }}
  ],
  "new_settings": [
    {{
      "name": "地点名",
      "type": "interior/exterior",
      "description": "场景描述（50字以上）"
    }}
  ],
  "plot_events": [
    {{
      "order": 1,
      "event": "事件描述",
      "characters_involved": ["参与角色"],
      "location": "地点",
      "source_text": "原文关键句"
    }}
  ],
  "dialogues": [
    {{
      "speaker": "说话者",
      "line": "单句对白（一字不改）"
    }}
  ]
}}

只输出 JSON，不要省略任何对话。"""

# ============================================================
# 1. 整体概述 Prompt — 轻量级，基于各章摘要生成全局视角
# ============================================================
OVERVIEW_PROMPT = """基于各章节的解构摘要，生成小说的整体概述。

## 各章摘要
{chapters_summary}

{json_rules}

## 输出 JSON
{{
  "meta": {{
    "title": "小说标题",
    "genre": ["类型"],
    "logline": "一句话概括（50字内）"
  }},
  "global_characters": [
    {{
      "id": "char_001",
      "name": "角色名",
      "role_type": "protagonist/antagonist/supporting/minor",
      "personality": ["合并各章的性格特征"],
      "background": "综合背景",
      "arc": "整体变化轨迹",
      "relationships": [
        {{"target_name": "关联角色", "relation": "关系", "description": "描述"}}
      ],
      "first_appearance_chapter": 1
    }}
  ],
  "global_settings": [
    {{
      "id": "loc_001",
      "name": "地点",
      "type": "interior/exterior",
      "description": "综合描述",
      "appears_in_chapters": [1]
    }}
  ]
}}

只输出 JSON。"""

# ============================================================
# 2. ScriptAgent — 基于解构数据一次性生成完整剧本
# ============================================================
SCRIPT_AGENT_PROMPT = """你是一位专业影视编剧。基于完整的小说解构数据，按标准剧本格式生成 YAML。

## ⚠️ 最重要的规则

### 对白规则（最关键！）
- **all_dialogues 中的每一个条目 = 剧本中的 1 个 dialogue beat**
- **绝对禁止将多句对白合并成 1 个 beat**。all_dialogues 有 N 条，剧本就必须有 N 个 dialogue beat
- 每句对白一字不改地引用 all_dialogues 中的 line 字段
- dialogue 的 character_name 必须与 characters 表中的 name 完全一致
- 同一个 speaker 连续说多句时，每句各自独立成 beat，中间可插入 action 或直接连续排列

### 场景规则
- 按 plot_timeline 的事件顺序拆分场景，地点切换或时间跳跃就新建 scene
- 一章情节丰富时拆成 2-4 个 scene
- 每个章节都必须有对应 scene

### 完整性自检
- 输出前逐一核对：all_dialogues 的 N 条对话 → 剧本中 N 个 dialogue beat
- 每个章节是否都有对应 scene

## 输入数据

### 章节列表
{chapters_info}

### 角色表
{characters_info}

### 场景地点
{settings_info}

### 情节时间线
{plot_timeline}

### 原文全部对话（每个条目 = 1句对白，全部必须出现在剧本中）
{all_dialogues}

## RAG 参考
{rag_context}

## 标准剧本格式说明

标准影视剧本中，对白是逐句呈现的，像这样：

```
场景标题
环境描述、人物动作

　　角色A：（情绪）对白内容
　　角色B：（情绪）对白内容
　　角色A：（情绪）回应内容
```

每句对白独立一行，角色名+冒号开头，这样才有对话的节奏感。

## Beat 类型
- action：动作、场景转换（description 30-100字，保留原文细节和氛围）
- dialogue：人物对白（每句对白一个 beat，来自 all_dialogues）
- monologue：角色内心独白（对应原文心理描写）
- narration：旁白叙述（世界观、背景等叙述性文字）

{json_rules}

## 输出 YAML 示例

以下是 2 句对白 + 1 个心理描写的正确写法。注意每句对白都是独立的 beat：

script:
  meta:
    title: "剧本标题"
    original_work: "原著名"
    original_author: "原著作者"
    version: "1.0"
    script_type: "movie"
    genre: ["类型"]
    logline: "一句话梗概"
    synopsis: "故事梗概（100-200字）"
    source_chapters:
      - chapter: 1
        title: "章标题"
  characters:
    - id: "char_001"
      name: "角色A"
      role_type: "protagonist"
      personality: ["特征"]
      background: "背景"
      arc: "弧光"
      relationships: []
  locations:
    - id: "loc_001"
      name: "地点名"
      type: "interior"
      description: "场景描述"
      props: []
  acts:
    - act_number: 1
      title: "幕标题"
      summary: "本幕概要"
      scenes:
        - scene_number: 1
          scene_title: "场景名"
          location_id: "loc_001"
          time: "日"
          summary: "本场概要"
          characters_present: ["char_001"]
          beats:
            - beat_number: 1
              type: "action"
              description: "动作/场景描述"
              source: "第1章"
            - beat_number: 2
              type: "monologue"
              character_id: "char_001"
              character_name: "角色A"
              description: "内心想法内容"
              emotion: "情绪"
              source: "第1章心理描写"
            - beat_number: 3
              type: "dialogue"
              character_id: "char_001"
              character_name: "角色A"
              dialogue: "第一句对白"
              emotion: "情绪"
              source: "第1章原对话"
            - beat_number: 4
              type: "action"
              description: "中间的动作"
              source: "第1章"
            - beat_number: 5
              type: "dialogue"
              character_id: "char_002"
              character_name: "角色B"
              dialogue: "第二句对白"
              emotion: "情绪"
              source: "第1章原对话"
          transition: "cut_to"

直接输出完整 YAML，不要省略任何对话，不要用 ```yaml 包裹。"""

# ============================================================
# RAG 查询改写 Prompt
# ============================================================
RAG_QUERY_REWRITE_PROMPT = """你是一个检索查询优化器。根据当前剧本创作阶段，将原始需求改写为更适合检索的查询。

## 当前阶段：{stage}
## 原著内容摘要：{context_summary}

请生成 2-3 个检索查询，用于从剧本知识库中检索相关参考案例。
查询应聚焦于：剧本结构、角色塑造、对白技巧、场景设计等与当前阶段相关的方面。

请以 JSON 数组格式返回：["查询1", "查询2", "查询3"]

只输出 JSON 数组。"""
