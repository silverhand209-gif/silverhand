# 剧本 YAML Schema 设计文档

## 1. 设计目标

本 Schema 用于将小说文本转换为结构化剧本，设计原则如下：

- **可读性优先**：YAML 格式天然适合人类阅读和编辑，作者可直接在文本编辑器中修改
- **结构化层次清晰**：从「作品 → 幕 → 场 → 节拍」四级嵌套，对应剧本创作的经典结构
- **行业兼容**：参照好莱坞剧本格式和中文剧本行业惯例
- **AI 友好**：层次分明、字段明确，便于 LLM 逐层生成和校验
- **可扩展**：通过自定义字段支持不同剧本类型（电影、电视剧、舞台剧）

## 2. 完整 Schema

```yaml
# ===================== 剧本 YAML Schema =====================
# 版本: 1.0
# 适用: 小说转剧本（电影/电视剧/舞台剧）

script:
  # ---------- 元信息 ----------
  meta:
    title: "剧本标题"                    # 必填，剧本名称
    original_work: "原著小说名"           # 必填，原著名称
    original_author: "原著作者"           # 必填
    adaptor: "改编者"                     # 选填，改编人
    version: "1.0"                       # 必填，剧本版本号
    script_type: "movie"                 # 必填，enum: [movie, tv_series, stage_play, web_series]
    genre:                               # 必填，类型标签列表
      - "悬疑"
      - "爱情"
    total_episodes: null                 # 电视剧/网剧时填写
    target_duration: "120分钟"           # 选填，预估时长
    logline: "一句话梗概"                # 必填，核心故事线
    synopsis: |                          # 必填，故事梗概（200-500字）
      详细的故事梗概...
    source_chapters:                     # 必填，改编所依据的原著章节
      - chapter: 1
        title: "第一章标题"
      - chapter: 2
        title: "第二章标题"
    created_at: "2024-01-01T00:00:00Z"  # 自动生成
    updated_at: "2024-01-01T00:00:00Z"  # 自动更新

  # ---------- 角色表 ----------
  characters:
    - id: "char_001"                     # 必填，唯一标识
      name: "角色姓名"                   # 必填
      aliases: ["别名1", "别名2"]        # 选填
      role_type: "protagonist"           # 必填，enum: [protagonist, antagonist, supporting, cameo, narrator]
      age: 28                            # 选填
      gender: "男"                       # 选填
      occupation: "职业"                 # 选填
      personality:                       # 必填，性格特征
        - "勇敢"
        - "冲动"
      background: |                      # 必填，角色背景故事
        角色的背景故事...
      arc: |                             # 必填，角色弧光（成长变化）
        角色在本剧中的成长轨迹...
      relationships:                     # 选填，与其他角色的关系
        - target_id: "char_002"
          relation: "恋人"
          description: "关系描述"
      notes: "补充说明"                  # 选填

  # ---------- 场景列表 ----------
  locations:
    - id: "loc_001"                      # 必填
      name: "场景名称"                   # 必填，如"林家客厅"
      type: "interior"                   # 必填，enum: [interior, exterior]
      description: "场景描述"            # 必填，环境细节
      time_period: "现代"                # 选填
      props:                             # 选填，关键道具
        - "道具1"
        - "道具2"

  # ---------- 分幕/分集 ----------
  acts:
    - act_number: 1                      # 必填，幕序号
      title: "第一幕 - 开端"             # 选填
      summary: "本幕概要"                # 必填
      scenes:                            # 必填，本幕包含的场景列表
        - scene_number: 1                # 必填，场序号（全剧唯一）
          scene_title: "第1场 - 初遇"    # 选填
          location_id: "loc_001"         # 必填，关联场景
          time: "日/夜/清晨/黄昏"        # 必填
          time_specific: "下午3点"       # 选填，具体时间
          summary: "本场概要"            # 必填
          characters_present:            # 必填，出场角色
            - "char_001"
            - "char_002"
          beats:                         # 必填，节拍序列
            - beat_number: 1             # 必填
              type: "action"             # 必填，enum: [action, dialogue, monologue, voiceover, transition, parenthetical]
              description: |             # 动作/场景描述（type=action 时填写）
                动作或场景描述文字...
              character_id: null         # 对白/独白/旁白时填写角色ID
              character_name: null       # 对白/独白/旁白时填写角色名（便于阅读）
              dialogue: null             # 对白内容（type=dialogue 时填写）
              parenthetical: null        # 括号指示（type=parenthetical 时填写，如"低声"）
              emotion: null              # 选填，情绪标注
              duration_seconds: null     # 选填，预估时长（秒）
              notes: null                # 选填，导演备注
            - beat_number: 2
              type: "dialogue"
              character_id: "char_001"
              character_name: "林默"
              dialogue: "你终于来了。"
              emotion: "平静中带着期待"
          transition: "cut_to"           # 选填，转场方式 enum: [cut_to, fade_in, fade_out, dissolve_to, smash_cut, match_cut]

  # ---------- 全局注释 ----------
  notes:                                 # 选填
    adaptation_notes: "改编说明"         # 改编思路说明
    director_notes: "导演建议"           # 导演视角建议
    unresolved:                          # 待解决问题列表
      - "第3章的感情线需要进一步展开"
```

## 3. 设计原因说明

### 3.1 为何选择 YAML 而非 JSON/XML/Fountain？

| 格式 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **YAML** | 人类可读写、支持多行文本、注释友好、层次清晰 | 对缩进敏感 | ✅ 最适合作者编辑 |
| JSON | 机器解析快 | 不支持注释、多行文本丑陋、括号嵌套难以阅读 | ❌ |
| XML | 结构化强 | 冗长、标签噪音大 | ❌ |
| Fountain | 剧本专用标记语言 | 生态较小、中文支持一般、结构不够丰富 | ❌ |

YAML 的核心优势在于「人类可编辑」+「机器可解析」的完美平衡。作者可以直接用 VS Code 打开 YAML 文件，语法高亮、折叠、校验一应俱全。

### 3.2 为何采用「幕 → 场 → 节拍」四级结构？

这是好莱坞经典三幕剧结构和中国影视剧本格式的融合：

- **幕（Act）**：对应三幕剧的「开端-发展-结局」或五幕剧结构，提供宏观节奏
- **场（Scene）**：对应剧本中的「场景编号」，是拍摄的基本单位，同一场景同一时间
- **节拍（Beat）**：剧本的最小叙事单元，可以是动作描述、对白、独白、旁白等

这种结构天然支持：
- AI 逐层生成（先规划幕→再生成场→最后细化节拍）
- 作者逐层编辑（可以先调整大结构再润色细节）
- 导出为标准剧本格式（如 PDF 剧本、分镜脚本）

### 3.3 节拍类型（beat.type）设计

| 类型 | 说明 | 示例 |
|------|------|------|
| `action` | 动作/场景描述 | "林默推开门，走进昏暗的房间" |
| `dialogue` | 角色对白 | 林默："你是谁？" |
| `monologue` | 独白（角色内心） | 林默（独白）："我该怎么办..." |
| `voiceover` | 旁白/画外音 | 旁白："这是一个关于选择的故事" |
| `transition` | 转场指示 | "画面渐黑" |
| `parenthetical` | 括号指示（表演提示） | "（低声）"、"（愤怒地）" |

这些类型覆盖了标准剧本格式中的所有元素，且每种类型有明确的字段关联（如 `dialogue` 需要 `character_id`，而 `action` 不需要）。

### 3.4 角色系统的设计考量

- `id` 使用 `char_001` 格式，便于在节拍中引用，避免角色重名问题
- `role_type` 区分主角/对手/配角/客串/叙述者，帮助 AI 把握叙事重心
- `arc`（角色弧光）是剧本区别于小说的关键——小说可以内心独白，剧本必须通过行动展现变化
- `relationships` 显式定义角色关系网络，便于 AI 生成有张力的对白

### 3.5 与标准剧本格式（如 Hollywood Standard）的兼容性

本 Schema 可以无损导出为：
- **PDF 剧本**（Courier 12pt，标准剧本排版）
- **Final Draft (.fdx)** 格式
- **Fountain** 标记语言
- **分镜脚本**（Shot List）

### 3.6 AI 生成策略

基于 LangGraph 的多 Agent 协作流程：

```
小说文本输入
    ↓
[ChapterAgent] 章节解析 → 提取章节结构、关键事件
    ↓
[CharacterAgent] 角色提取 → 识别角色、性格、关系
    ↓
[PlotAgent] 情节重构 → 构建幕-场结构
    ↓
[DialogueAgent] 对白生成 → 叙事转对白、独白
    ↓
[SceneAgent] 场景描述 → 环境、动作、转场
    ↓
[AssemblyAgent] 整合校验 → YAML 输出、一致性检查
    ↓
[RAG] 提供剧本创作知识参考（经典剧本片段、对白范例）
```

每个 Agent 独立负责一个维度，通过 Supervisor 协调，保证生成质量。
