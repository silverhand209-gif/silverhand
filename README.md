# 📜 小说转剧本 — AI 辅助剧本创作工具

基于 **LangGraph 多智能体框架** + **RAG 检索增强生成** 的 AI 辅助剧本创作工具，将 3 个章节以上的小说文本自动转换为结构化剧本（YAML 格式）。

<p align="center">
  <img src="https://img.shields.io/badge/React-18-blue?logo=react" alt="React">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-0.2+-orange" alt="LangGraph">
  <img src="https://img.shields.io/badge/ChromaDB-向量数据库-8A2BE2" alt="ChromaDB">
  <img src="https://img.shields.io/badge/TDesign-1.10+-0052D9?logo=tencent" alt="TDesign">
</p>

## ✨ 核心特性

- **📚 多章节处理**：上传 `.txt` 小说文件，自动识别「第X章」进行章节分割
- **🤖 6 大智能体协作**：基于 LangGraph 编排的专业 Agent 流水线
  - `ChapterAgent` — 章节结构解析与关键事件提取
  - `CharacterAgent` — 角色识别、性格分析与关系图谱
  - `PlotAgent` — 情节重构（幕-场-节拍三级结构）
  - `DialogueAgent` — 叙事转对白、独白与旁白生成
  - `SceneAgent` — 场景描述、氛围设计与转场
  - `AssemblyAgent` — 整合校验与 YAML 格式化输出
- **🔍 RAG 知识增强**：ChromaDB 向量数据库 + Sentence-Transformers 嵌入，自动检索经典剧本参考
- **📝 标准化 YAML 输出**：好莱坞剧本格式兼容，支持导出与二次编辑
- **📊 SSE 流式进度**：实时推送各 Agent 执行状态与生成进度
- **📋 版本管理**：支持剧本多版本保存与历史回溯
- **🎨 现代化 UI**：紫蓝渐变主题，TDesign 组件库深度定制，响应式布局

## 🏗️ 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                  前端 (React 18 + TDesign + Vite)            │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ 项目列表  │  │ 小说上传/粘贴 │  │ 剧本预览/编辑  │          │
│  │ 知识库管理 │  │ 生成进度监控  │  │ 版本历史管理  │          │
│  └──────────┘  └──────────────┘  └──────────────┘          │
└────────────────────────┬────────────────────────────────────┘
                         │ SSE / REST API
┌────────────────────────┴────────────────────────────────────┐
│                   后端 (FastAPI + Python)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              LangGraph Multi-Agent Pipeline           │   │
│  │  Chapter → Character → Plot → Dialogue → Scene       │   │
│  │                    → Assembly                         │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────────┐     │
│  │   RAG 引擎    │  │  SQLite  │  │    ChromaDB       │     │
│  │ (ChromaDB +  │  │  项目存储  │  │   向量知识库      │     │
│  │  Embedding)  │  │          │  │                   │     │
│  └──────────────┘  └──────────┘  └───────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 前置要求

| 依赖 | 版本 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+ |
| LLM API | OpenAI 兼容接口（Key + Base URL） |

### 1. 克隆并安装

```bash
# 安装后端依赖
cd backend
pip install -r requirements.txt

# 安装前端依赖（在项目根目录）
cd ..
npm install
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入你的 LLM API Key 和配置
```

关键配置项：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | LLM API Key（必填） | — |
| `LLM_BASE_URL` | API 地址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 主模型（负责核心生成） | 请替换为你的模型名 |
| `LLM_SMALL_MODEL` | 轻量模型（RAG 查询改写） | 请替换为你的模型名 |
| `EMBEDDING_MODEL` | 嵌入模型 | `BAAI/bge-small-zh-v1.5` |
| `EMBEDDING_DEVICE` | 嵌入设备 | `cpu` |
| `PORT` | 后端端口 | `8000` |
| `MAX_UPLOAD_SIZE_MB` | 上传文件大小限制 | `50` |

### 3. 启动服务

```bash
npm run dev
```

一条命令即可同时启动后端（端口 8000）和前端（端口 5173）。

> 首次使用或换新环境时，推荐先运行 `start.bat`（Windows），它会自动安装依赖并检查环境配置。

### 4. 访问应用

打开浏览器访问 **http://localhost:5173**

> 前端通过 Vite proxy 将 `/api` 请求转发到后端 `localhost:8000`，无需额外配置跨域。

## 📖 使用指南

### 创建剧本项目

1. 首页点击 **「新建项目」**，填写项目名称、原著信息、剧本类型（电影/电视剧/网剧/舞台剧）
2. 进入项目页，在 **「上传小说」** 标签页上传 `.txt` 文件，或点击「从剪贴板粘贴」
3. 系统自动识别章节分割，确认章节数量 ≥ 3 后，点击 **「开始生成剧本」**
4. 可在 **「生成进度」** 标签页实时查看 6 个 Agent 的执行状态和整体百分比

### 编辑与管理剧本

1. 生成完成后自动切换到 **「剧本预览」** 标签页
2. 在深色主题编辑器中直接修改 YAML 内容，点击 **「保存修改」**
3. 支持 **下载 YAML 文件** 或保存为新版本
4. 版本历史在页面下方展示，可随时回溯

### 知识库管理

- 在 **「知识库」** 页面可以搜索和添加剧本创作参考知识
- 添加的知识条目会自动向量化并纳入 RAG 检索范围
- AI 在生成各环节时会检索相关知识作为创作参考
- 搜索结果展示相关度百分比，支持展开查看完整内容

## 📄 YAML 剧本格式

输出剧本采用 **幕 → 场 → 节拍** 四级嵌套结构，完整 Schema 定义请参阅 **[SCHEMA.md](./SCHEMA.md)**。

```
script
├── meta              # 元信息：标题、原著、类型、梗概等
├── characters[]      # 角色表：姓名、性格、关系网络、角色弧光
├── locations[]       # 场景列表：内外景、描述、道具
├── acts[]            # 分幕
│   └── scenes[]      #   分场
│       └── beats[]   #     节拍：对白/动作/独白/旁白/转场
└── notes             # 改编说明、导演建议
```

## 📁 项目结构

```
novel-to-script/
├── backend/
│   ├── main.py              # FastAPI 服务入口（路由、SSE、文件上传）
│   ├── agent_graph.py       # LangGraph 多智能体编排（6 Agent 流水线）
│   ├── prompts.py           # Prompt 模板 + JSON 输出约束规则
│   ├── rag.py               # RAG 引擎（ChromaDB + Sentence-Transformers）
│   ├── db.py                # SQLite 数据访问层（项目、版本 CRUD）
│   ├── config.py            # 环境变量配置管理
│   ├── requirements.txt     # Python 依赖
│   └── .env.example         # 环境变量模板
├── src/
│   ├── main.tsx             # React 入口
│   ├── App.tsx              # 路由配置（/、/project/:id、/knowledge）
│   ├── api.ts               # Axios API 封装 + SSE 流式调用
│   ├── store.ts             # Zustand 状态管理（生成进度、剧本内容）
│   ├── index.css            # 全局样式（TDesign 组件深度定制）
│   ├── components/
│   │   └── Layout.tsx       # 页面布局（Header / Content / Footer）
│   └── pages/
│       ├── HomePage.tsx     # 项目列表页（创建、删除、搜索）
│       ├── ProjectPage.tsx  # 项目详情页（上传、生成、预览、版本管理）
│       └── KnowledgePage.tsx# 知识库管理页（搜索、添加、统计）
├── SCHEMA.md                # YAML Schema 设计文档
├── package.json             # 前端依赖与脚本
├── vite.config.ts           # Vite 配置（代理 /api → :8000）
├── tsconfig.json            # TypeScript 配置
├── tailwind.config.js       # Tailwind CSS 配置
├── postcss.config.js        # PostCSS 配置
├── index.html               # HTML 入口
├── start.bat                # Windows 一键启动脚本
└── README.md                # 项目说明
```

## 🛠️ 技术栈

### 前端
- **React 18** + TypeScript
- **TDesign React** v1.10+ — 腾讯开源企业级 UI 组件库
- **React Router v6** — SPA 路由
- **Zustand** — 轻量级状态管理
- **Axios** — HTTP 请求 + SSE 流式数据
- **Vite 6** — 构建工具
- **Tailwind CSS** — 原子化 CSS 框架

### 后端
- **FastAPI** — 高性能 Python Web 框架
- **LangGraph** — LLM 多智能体编排框架
- **ChromaDB** — 向量数据库（RAG 知识库）
- **Sentence-Transformers** — 文本嵌入模型
- **SQLite** — 轻量级项目数据存储
- **json-repair** — LLM JSON 输出自动修复

### 生成流水线

```
小说文本 → ChapterAgent → CharacterAgent → PlotAgent
         → DialogueAgent → SceneAgent → AssemblyAgent
         → YAML 剧本
              ↑
         RAG 知识检索（贯穿全程）
```

每个 Agent 独立负责一个创作维度，前一阶段输出作为后一阶段输入，最终由 AssemblyAgent 整合校验并输出标准化 YAML。

## ⚠️ 常见问题

### 1. 前端报 `ECONNREFUSED` 错误？

这是后端未启动或未就绪时的正常现象，Vite proxy 已静默处理。请确保先启动后端 `python backend/main.py` 再访问前端。

### 2. 首次启动下载嵌入模型很慢？

`start.bat` 已设置 `HF_ENDPOINT=https://hf-mirror.com`（Hugging Face 镜像）加速下载。如仍较慢，可手动执行：

```bash
export HF_ENDPOINT=https://hf-mirror.com   # Linux/Mac
set HF_ENDPOINT=https://hf-mirror.com      # Windows
```

### 3. JSON 解析错误？

项目已集成 `json-repair` 库自动修复 LLM 输出中的 JSON 格式错误，同时在 Prompt 层面加入了严格的 JSON 输出约束。如仍有问题，请检查 LLM API 是否稳定。

### 4. 如何切换 LLM 提供商？

编辑 `backend/.env`，修改 `LLM_BASE_URL` 和 `LLM_MODEL` 即可。兼容所有 OpenAI 接口格式的服务（如 DeepSeek、通义千问、智谱 GLM 等）。

## 📄 License

MIT
