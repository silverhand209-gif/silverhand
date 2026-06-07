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
# 1. DeconstructorAgent — 一次性原文解构（唯一读原文的 Agent）
# ============================================================
DECONSTRUCTOR_AGENT_PROMPT = """你是一位严谨的文学分析师。唯一任务：将小说原文完整解构为结构化数据，供剧本生成使用。

## ⚠️ 完整性要求（最重要）

### all_dialogues — 对话提取规则（必须逐句提取！）
- 逐句通读原文，找到**每一句**用引号包裹的人物对白，**每句一个独立条目**
- 包括：直接引号对话、转述对话、自言自语、人群喊话嘲讽议论
- **绝对禁止**：把多句对话合并成1条。原文有30句对话就必须有30个条目
- **示例**：原文 A："你好。" B："你好吗？" C："再见。" → 3个条目，不是1个
- 简化输出：每个条目只需要 speaker、line 两个必填字段

### characters — 角色提取规则
- 列出原文中**每一个**有名字的角色，包括只出场一次的角色

### settings — 场景提取规则
- 列出原文中出现的**每一个**场景地点，详细描述原文中的描写

### plot_timeline — 情节提取规则
- 按原文时间顺序列出**每一个**关键事件，不得遗漏

## 核心原则：绝对忠实于原文
- 禁止编造：所有内容必须在原文中有对应文字
- 禁止猜测：原文未明确的信息标注为 null 或空字符串
- 禁止添加：不得添加原文中不存在的角色、情节、场景、对话
- 完整覆盖：必须覆盖原文中每一个有名角色、每一个场景、每一段对话

## 小说全文
{novel_text}

## RAG 参考
{rag_context}

{json_rules}

## 输出 JSON Schema
{{
  "meta": {{
    "title": "原文标题",
    "author": null,
    "genre": ["类型"],
    "logline": "一句话概括核心冲突（50字内）"
  }},
  "chapters": [
    {{
      "chapter_number": 1,
      "title": "章节标题",
      "summary": "本章实际发生的情节（100-300字，覆盖所有关键情节）",
      "key_events": ["按顺序列出本章每一个关键事件，不要合并"],
      "characters_appeared": ["本章出场的每一个有名角色，包括配角"],
      "locations": ["本章出现的每一个场景地点"]
    }}
  ],
  "characters": [
    {{
      "id": "char_001",
      "name": "原文中的真实姓名",
      "aliases": ["原文中的其他称呼"],
      "role_type": "protagonist/antagonist/supporting/minor",
      "personality": ["原文体现的性格特征，尽可能多列"],
      "background": "原文中明确提及的背景信息",
      "arc": "角色在本文范围内的变化轨迹",
      "dialogue_style": "从原文对白总结的说话风格",
      "dialogue_samples": ["原文中该角色至少2句真实对白"],
      "relationships": [
        {{
          "target_name": "关联角色名",
          "relation": "原文描述的关系",
          "description": "原文中的关系描述"
        }}
      ],
      "first_appearance_chapter": 1
    }}
  ],
  "settings": [
    {{
      "id": "loc_001",
      "name": "原文中的地点名称",
      "type": "interior/exterior",
      "description": "原文对场景的详细描写（包含氛围、光线、时间、人群等原文细节，100字以上）",
      "appears_in_chapters": [1]
    }}
  ],
  "plot_timeline": [
    {{
      "order": 1,
      "chapter": 1,
      "event": "原文中实际发生的具体事件描述（50-100字）",
      "characters_involved": ["参与角色"],
      "location": "发生地点名",
      "source_text": "对应的原文关键句（50字内）"
    }}
  ],
  "all_dialogues": [
    {{
      "chapter": 1,
      "speaker": "原文说话者姓名（没有名字的用'路人甲'/'测验员'等描述）",
      "line": "原文中的单句对白（一字不改，去掉引号，每句一个条目）"
    }}
  ]
}}

只输出 JSON，不要省略任何内容。"""

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
