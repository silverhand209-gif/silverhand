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
      "summary": "本章实际发生的情节（80-200字）",
      "key_events": ["关键事件"],
      "characters_appeared": ["出场的所有有名角色"],
      "locations": ["出现的场景地点"]
    }}
  ],
  "characters": [
    {{
      "id": "char_001",
      "name": "原文中的真实姓名",
      "aliases": ["原文中的其他称呼"],
      "role_type": "protagonist",
      "personality": ["原文体现的性格特征"],
      "background": "原文中明确提及的背景",
      "arc": "角色在原文中的变化轨迹",
      "dialogue_style": "从原文对白总结的说话风格",
      "dialogue_samples": ["原文中该角色的真实对白"],
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
      "type": "interior",
      "description": "原文对场景的具体描述（若无则写'原文未详述'）",
      "appears_in_chapters": [1]
    }}
  ],
  "plot_timeline": [
    {{
      "order": 1,
      "chapter": 1,
      "event": "原文中实际发生的事件描述",
      "characters_involved": ["参与角色"],
      "location": "发生地点名",
      "source_text": "对应的原文关键句（50字内）"
    }}
  ],
  "all_dialogues": [
    {{
      "chapter": 1,
      "speaker": "原文说话者",
      "listener": "原文听话者（可为null）",
      "line": "原文中的完整对白（一字不改）",
      "context": "对话情境（30-80字）",
      "emotion": "原文体现的情绪"
    }}
  ]
}}

只输出 JSON。"""

# ============================================================
# 2. ScriptAgent — 基于解构数据一次性生成完整剧本
# ============================================================
SCRIPT_AGENT_PROMPT = """你是一位专业影视编剧。基于完整的小说解构数据，一次性生成标准 YAML 剧本。

## ⚠️ 最重要规则：必须覆盖每一章
- chapters 列表中有多少章，就必须在 acts 中覆盖到每一章
- **每章至少对应一个 scene**，情节密集的章节可拆分为多个 scene
- 绝对禁止只输出 1 个 act 或 1 个 scene 就结束
- 输出前自检：acts 中所有 scenes 的 source 标注覆盖了 chapters 的每一个章节号

## 核心原则：绝对忠实于原著
- 所有对白必须来自 all_dialogues 中的原文对白，不得改写或编造
- 所有角色必须在 characters 表中存在
- 所有地点必须在 settings 表中存在
- 情节按 plot_timeline 的顺序展开，不得遗漏事件
- 每个 beat 必须标注 source 字段，标明来自第几章

## 输入数据

### 章节列表（共 N 章，必须全部覆盖）
{chapters_info}

### 角色表（含说话风格和原文对白样本）
{characters_info}

### 场景地点
{settings_info}

### 情节时间线
{plot_timeline}

### 原文全部对话
{all_dialogues}

## RAG 参考
{rag_context}

## 创作约束
1. 对白优先直接引用 all_dialogues 中的原文对话
2. 叙事文字可转化为 action 类型节拍，保留原文意思
3. monologue 类型仅用于原文中有内心描写的角色
4. 幕场结构按 plot_timeline 时间顺序排列
5. 一场可包含同一章节的多个连续事件
6. 对话节拍中 character_name 必须与 characters 表中的 name 完全一致

{json_rules}

## 输出 YAML（直接输出，不要代码块）

假设有 3 章，输出结构应类似（根据实际章节数扩展）：

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
        title: "第1章标题"
      - chapter: 2
        title: "第2章标题"
      - chapter: 3
        title: "第3章标题"
  characters:
    - id: "char_001"
      name: "角色名"
      role_type: "protagonist"
      personality: ["特征"]
      background: "背景"
      arc: "角色弧光"
      relationships:
        - target_id: "char_002"
          relation: "关系"
          description: "描述"
  locations:
    - id: "loc_001"
      name: "场景名"
      type: "interior"
      description: "描述"
      props: ["道具"]
  acts:
    - act_number: 1
      title: "第1幕 - 开端"
      summary: "本幕涵盖第1章内容"
      scenes:
        - scene_number: 1
          scene_title: "第1场 - 具体场景名"
          location_id: "loc_001"
          time: "日"
          summary: "场概要"
          characters_present: ["char_001"]
          beats:
            - beat_number: 1
              type: "action"
              description: "基于原文的动作描述"
              source: "第1章"
            - beat_number: 2
              type: "dialogue"
              character_id: "char_001"
              character_name: "角色名"
              dialogue: "原文对白"
              emotion: "情绪"
              source: "第1章原对话"
          transition: "cut_to"
        - scene_number: 2
          scene_title: "第2场 - 具体场景名"
          location_id: "loc_002"
          time: "日"
          summary: "场概要"
          characters_present: ["char_001", "char_002"]
          beats:
            - beat_number: 1
              type: "action"
              description: "动作描述"
              source: "第1章"
            - beat_number: 2
              type: "dialogue"
              character_id: "char_001"
              character_name: "角色名"
              dialogue: "原文对白"
              emotion: "情绪"
              source: "第1章原对话"
          transition: "cut_to"
    - act_number: 2
      title: "第2幕 - 发展"
      summary: "本幕涵盖第2章内容"
      scenes:
        - scene_number: 3
          scene_title: "第3场 - 具体场景名"
          location_id: "loc_003"
          time: "夜"
          summary: "场概要"
          characters_present: ["char_001"]
          beats:
            - beat_number: 1
              type: "action"
              description: "动作描述"
              source: "第2章"
            - beat_number: 2
              type: "dialogue"
              character_id: "char_001"
              character_name: "角色名"
              dialogue: "原文对白"
              emotion: "情绪"
              source: "第2章原对话"
          transition: "cut_to"
    - act_number: 3
      title: "第3幕 - 高潮/结尾"
      summary: "本幕涵盖第3章内容"
      scenes:
        - scene_number: 4
          scene_title: "第4场 - 具体场景名"
          location_id: "loc_001"
          time: "日"
          summary: "场概要"
          characters_present: ["char_001", "char_002"]
          beats:
            - beat_number: 1
              type: "action"
              description: "动作描述"
              source: "第3章"
            - beat_number: 2
              type: "dialogue"
              character_id: "char_001"
              character_name: "角色名"
              dialogue: "原文对白"
              emotion: "情绪"
              source: "第3章原对话"
          transition: "fade_out"
  notes:
    adaptation_notes: "改编说明"
    chapters_to_acts_mapping: "第1章→第1幕，第2章→第2幕，第3章→第3幕"

直接输出 YAML 内容，不要包含任何解释文字，不要用 ```yaml 包裹。"""

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
