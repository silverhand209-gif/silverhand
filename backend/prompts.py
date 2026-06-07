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
- all_dialogues 必须提取原文中**每一句**人物对白，一字不漏。包括：
  * 直接引号内的对话
  * 叙述中转述的对话（如"某某说……"）
  * 人物内心的自言自语（作为 monologue 或内心对白）
  * 人群中的喊话、嘲讽、议论
- characters 必须列出原文中**每一个**有名字的角色，包括只出场一次的角色
- settings 必须列出原文中出现的**每一个**场景地点，详细描述原文中对场景的描写
- plot_timeline 按原文时间顺序列出**每一个**关键事件，不得遗漏

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
      "speaker": "原文说话者姓名",
      "listener": "原文听话者姓名（可为null）",
      "line": "原文中的完整对白段落（一字不改，保留原文换行和标点）",
      "context": "对话发生的前因后果（30-80字）",
      "emotion": "原文体现的情绪"
    }}
  ]
}}

只输出 JSON，不要省略任何内容。"""

# ============================================================
# 2. ScriptAgent — 基于解构数据一次性生成完整剧本
# ============================================================
SCRIPT_AGENT_PROMPT = """你是一位专业影视编剧。基于完整的小说解构数据，生成标准 YAML 剧本。

## ⚠️ 最重要规则：丰富完整输出
- 必须覆盖 chapters 中列出的**每一章**
- **根据 plot_timeline 的事件密度拆分场景**：每个场景切换/地点切换应新建一个 scene
- 一章情节丰富的，应拆成 2-4 个 scene，不要强行压缩到 1 个 scene
- **all_dialogues 中的每一句对白都要在剧本中出现**，不能选择性遗漏
- 绝对禁止只输出 1 个 act 或 1 个 scene 就结束
- 输出前自检：all_dialogues 的对话是否全部覆盖、每个章节是否都有对应 scene

## 核心原则：绝对忠实于原著
- 所有对白必须来自 all_dialogues 中的原文对白，不得改写或编造
- 所有角色必须在 characters 表中存在
- 所有地点必须在 settings 表中存在，场景描述引用 settings 中的详细描写
- 情节按 plot_timeline 的顺序展开，不得遗漏事件
- 每个 beat 必须标注 source 字段，标明来自第几章

## 输入数据

### 章节列表（共 N 章，必须全部覆盖）
{chapters_info}

### 角色表（含说话风格和原文对白样本）
{characters_info}

### 场景地点（含详细描写，请充分使用）
{settings_info}

### 情节时间线（按此顺序编排场景）
{plot_timeline}

### 原文全部对话（每一句都要在剧本中出现）
{all_dialogues}

## RAG 参考
{rag_context}

## 创作指南
1. **场景拆分**：按 plot_timeline 的事件顺序，每遇到地点切换或时间跳跃就新建 scene
2. **对白完整性**：将 all_dialogues 中的每一句对话分配到合适的 scene 中，不允许遗漏
3. **动作描述**：action 类型 beat 的 description 要详细（30-100字），保留原文的细节和氛围
4. **内心独白**：原文中有心理描写的，使用 monologue 类型 beat 表现角色内心活动
5. **角色一致性**：dialogue/monologue 中的 character_name 必须与 characters 表完全一致
6. **场景描述**：scene 的 summary 应包含场景的氛围、光线、人物状态等原文细节

## Beat 类型说明
- action：动作、行为、场景转换
- dialogue：人物对白，来自 all_dialogues
- monologue：角色内心独白（对应原文心理描写）
- narration：旁白叙述（用于交代世界观、背景等原文叙述性文字）

{json_rules}

## 输出 YAML（直接输出，不要代码块）

YAML 结构如下。注意：以下仅为格式参考，你必须根据实际输入数据生成完整内容，不要照抄示例数据。

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
      personality: ["特征1", "特征2"]
      background: "背景信息"
      arc: "角色弧光"
      relationships:
        - target_id: "char_002"
          relation: "关系"
          description: "关系描述"
  locations:
    - id: "loc_001"
      name: "场景名"
      type: "interior"
      description: "引用 settings 中的详细场景描述"
      props: ["道具"]
  acts:
    - act_number: 1
      title: "幕标题"
      summary: "本幕涵盖的内容概要"
      scenes:
        - scene_number: 1
          scene_title: "具体场景标题"
          location_id: "loc_001"
          time: "日"
          summary: "本场发生的情节概要"
          characters_present: ["char_001"]
          beats:
            - beat_number: 1
              type: "action"
              description: "详细的动作/场景描述"
              source: "第1章"
            - beat_number: 2
              type: "monologue"
              character_id: "char_001"
              character_name: "角色名"
              description: "内心独白内容"
              emotion: "情绪"
              source: "第1章心理描写"
            - beat_number: 3
              type: "dialogue"
              character_id: "char_001"
              character_name: "角色名"
              dialogue: "原文对白（完整引用）"
              emotion: "情绪"
              source: "第1章原对话"
            - beat_number: 4
              type: "narration"
              description: "旁白叙述内容"
              source: "第1章叙述"
          transition: "cut_to"
        - scene_number: 2
          scene_title: "下一场场景标题"
          location_id: "loc_002"
          time: "夜"
          summary: "本场发生的情节概要"
          characters_present: ["char_001", "char_002"]
          beats:
            - beat_number: 1
              type: "action"
              description: "详细的动作/场景描述"
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
      title: "下一幕标题"
      summary: "本幕涵盖的内容概要"
      scenes:
        - scene_number: 3
          scene_title: "具体场景标题"
          location_id: "loc_003"
          time: "日"
          summary: "本场发生的情节概要"
          characters_present: ["char_001", "char_003"]
          beats:
            - beat_number: 1
              type: "action"
              description: "详细的动作/场景描述"
              source: "第2章"
            - beat_number: 2
              type: "narration"
              description: "旁白叙述"
              source: "第2章叙述"
            - beat_number: 3
              type: "dialogue"
              character_id: "char_001"
              character_name: "角色名"
              dialogue: "原文对白"
              emotion: "情绪"
              source: "第2章原对话"
          transition: "cut_to"
  notes:
    adaptation_notes: "改编说明"
    chapters_to_acts_mapping: "各章节对应的幕/场说明"

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
