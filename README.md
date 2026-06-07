# 📜 小说转剧本 — AI 辅助剧本创作工具

基于 **LangGraph 多智能体框架** + **RAG 检索增强生成** 的 AI 辅助剧本创作工具，将小说文本自动转换为结构化剧本（YAML 格式）。支持**分章批处理**，可处理任意章节数量。

<p align="center">
  <img src="https://img.shields.io/badge/React-18-blue?logo=react" alt="React">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-0.2+-orange" alt="LangGraph">
  <img src="https://img.shields.io/badge/ChromaDB-向量数据库-8A2BE2" alt="ChromaDB">
  <img src="https://img.shields.io/badge/TDesign-1.10+-0052D9?logo=tencent" alt="TDesign">
</p>

## ✨ 核心特性

- **📚 分章批处理**：自动识别「第X章」进行章节分割，逐章独立解构后增量累积，支持无限章节扩展
- **🤖 4 Agent 串行流水线**：基于 LangGraph 编排的专业 Agent 工作流
  - `DeconstructorAgent` — 逐章循环解构，提取角色、场景、情节事件、对白
  - `OverviewAgent` — 全局整合，生成角色关系网络与场景综合描述
  - `ScriptAgent` — 剧本生成，基于完整解构数据一次性输出 YAML 剧本
  - `AssemblyAgent` — 纯程序校验，检查 YAML 完整性与角色引用一致性
- **🔍 RAG 知识增强**：ChromaDB 向量数据库 + Sentence-Transformers 嵌入，自动检索经典剧本参考
- **📝 标准化 YAML 输出**：好莱坞剧本格式兼容（幕→场→节拍四级结构），支持导出与二次编辑
- **📊 SSE 流式进度**：实时推送各 Agent 执行状态与生成进度
- **📋 版本管理**：支持剧本多版本保存与历史回溯
- **🎨 现代化 UI**：渐变背景 + 暗色剧本编辑器，TDesign 组件库深度定制，响应式布局

## 🎬 Demo 演示

[![小说转剧本 Demo](https://img.shields.io/badge/bilibili-演示视频-00A1D6?logo=bilibili)](https://www.bilibili.com/video/BV1vbEh6bE4d/)

点击上方观看完整操作演示（B站）。

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
│  │          LangGraph 4 Agent 串行流水线                  │   │
│  │  Deconstructor（逐章循环）→ Overview → Script → Assembly│   │
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
3. 系统自动识别章节分割，点击 **「开始生成剧本」**
4. 可在 **「生成进度」** 标签页实时查看 4 个 Agent 的执行状态和整体百分比

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
│   ├── agent_graph.py       # LangGraph 4 Agent 串行编排（支持分章批处理）
│   ├── prompts.py           # Prompt 模板（逐章解构、全局整合、剧本生成）
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
│   ├── index.css            # 全局样式（渐变背景、暗色编辑器、组件定制）
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
小说文本 → 章节分割
              ↓
         DeconstructorAgent（逐章循环）
         每章独立提取：角色、场景、情节、对白
         增量累积，去重合并
              ↓
         OverviewAgent（全局整合）
         角色关系网络、场景综合描述、元信息
              ↓
         ScriptAgent（剧本生成）
         动态 token 预算，一次性生成完整 YAML
              ↓
         AssemblyAgent（纯程序校验）
         YAML 字段完整性、角色引用一致性、对白数量
              ↓
         YAML 剧本
              ↑
         RAG 知识检索（贯穿 Overview + Script 阶段）
```

**架构优势**：
- **逐章解构**：每章独立调用 LLM，单次输出可控（4K tokens），不受总章节数限制
- **增量累积**：角色按名称去重合并，场景和情节按顺序追加，天然支持跨章节关联
- **动态预算**：ScriptAgent 的 `max_tokens` 根据章节数动态计算 `max(16384, chapters × 2048)`

## 📝 更新日志

### 2026-06-07 — PR #4 & #5 合并

| PR | 内容 |
|----|------|
| [#4](https://github.com/silverhand209-gif/silverhand/pull/4) | **3 Agent 串行 + 分章批处理架构** — 从 6 Agent 重构为 Deconstructor→Overview→Script→Assembly 4 Agent 流水线；实现逐章循环解构 + 增量累积，支持无限章节扩展；修复对白大量缺失问题，每句对白独立 beat |
| [#5](https://github.com/silverhand209-gif/silverhand/pull/5) | **前端 UI 优化** — 剧本预览区暗色编辑器（#1e1e2e 背景 + 语法高亮配色）；页面渐变背景；Card 组件圆角统一 14px；空状态结构化样式；操作栏样式抽取 |

## 📄 License

MIT
