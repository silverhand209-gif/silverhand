"""FastAPI 后端主服务 - 小说转剧本 Web 应用"""
import json
import uuid
import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from db import (
    init_db, create_project, get_project, list_projects,
    update_project, delete_project, save_chapter, get_chapters,
    save_agent_log, get_agent_logs, save_script_version, get_script_versions
)
from agent_graph import run_script_generation
from rag import init_knowledge_base, get_knowledge_stats, add_knowledge, search_knowledge

# ============================================================
# App 初始化
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    await init_db()
    await init_knowledge_base()
    print(f"[Server] 服务已启动: http://{settings.HOST}:{settings.PORT}")
    yield
    # 关闭时（可在此清理资源）

app = FastAPI(
    title="小说转剧本 - AI 辅助剧本创作工具",
    description="基于 LangGraph 多智能体框架的小说转剧本工具",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Pydantic Models
# ============================================================
class ProjectCreate(BaseModel):
    title: str
    original_work: str = ""
    original_author: str = ""
    script_type: str = "movie"


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    original_work: Optional[str] = None
    original_author: Optional[str] = None
    script_type: Optional[str] = None
    script_yaml: Optional[str] = None


class ChapterCreate(BaseModel):
    chapter_number: int
    title: str
    content: str


class KnowledgeAdd(BaseModel):
    title: str
    content: str
    category: str = "用户添加"


# ============================================================
# 项目 API
# ============================================================
@app.get("/api/projects")
async def api_list_projects():
    """获取项目列表"""
    projects = await list_projects()
    return {"projects": projects}


@app.post("/api/projects")
async def api_create_project(project: ProjectCreate):
    """创建新项目"""
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    result = await create_project(
        project_id=project_id,
        title=project.title,
        original_work=project.original_work,
        original_author=project.original_author,
        script_type=project.script_type
    )
    return {"project": result}


@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: str):
    """获取项目详情"""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    chapters = await get_chapters(project_id)
    versions = await get_script_versions(project_id)
    logs = await get_agent_logs(project_id)
    return {
        "project": project,
        "chapters": chapters,
        "versions": versions,
        "agent_logs": logs
    }


@app.put("/api/projects/{project_id}")
async def api_update_project(project_id: str, update: ProjectUpdate):
    """更新项目"""
    kwargs = {k: v for k, v in update.model_dump().items() if v is not None}
    if not kwargs:
        raise HTTPException(status_code=400, detail="无更新内容")
    result = await update_project(project_id, **kwargs)
    if not result:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": result}


@app.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: str):
    """删除项目"""
    success = await delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"message": "删除成功"}


# ============================================================
# 小说上传 & 章节管理
# ============================================================
@app.post("/api/projects/{project_id}/upload")
async def api_upload_novel(
    project_id: str,
    file: UploadFile = File(...),
    chapter_mode: str = Form("auto")  # auto: 自动分割, manual: 整体上传
):
    """上传小说文件（支持 .txt）"""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 读取文件
    content = await file.read()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("gbk")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="文件编码不支持，请使用 UTF-8 或 GBK 编码")

    if len(text) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"文件大小超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制")

    # 自动分割章节（通过 "第X章" 模式匹配）
    import re
    chapter_pattern = re.compile(r'(?:第\s*([一二三四五六七八九十百千万\d]+)\s*章[^\n]*)')
    splits = list(chapter_pattern.finditer(text))

    chapters = []
    if len(splits) >= 3 and chapter_mode == "auto":
        # 按章节分割
        for i, match in enumerate(splits):
            chapter_title = match.group(0).strip()
            start = match.start()
            end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
            chapter_content = text[start:end].strip()

            # 尝试解析章节号
            chapter_num = match.group(1)
            try:
                num = int(chapter_num)
            except ValueError:
                # 中文数字转阿拉伯数字
                num = _cn_num_to_int(chapter_num)

            ch = await save_chapter(project_id, num, chapter_title, chapter_content)
            chapters.append(ch)
    else:
        # 整体上传
        ch = await save_chapter(project_id, 1, "全文", text)
        chapters.append(ch)

    # 拼接小说全文并更新项目
    full_text = "\n\n".join([c["content"] for c in chapters])
    await update_project(
        project_id,
        novel_text=full_text,
        chapter_count=len(chapters)
    )

    return {
        "message": f"上传成功，共 {len(chapters)} 章",
        "chapters": chapters,
        "total_chars": len(full_text)
    }


def _cn_num_to_int(cn: str) -> int:
    """中文数字转阿拉伯数字（简单版）"""
    mapping = {
        "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
        "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        "百": 100, "千": 1000, "万": 10000,
        "零": 0, "两": 2
    }
    result = 0
    temp = 0
    for char in cn:
        if char in mapping:
            val = mapping[char]
            if val >= 10:
                if temp == 0:
                    temp = 1
                result += temp * val
                temp = 0
            else:
                temp = val
        else:
            try:
                return int(cn)
            except ValueError:
                return 0
    result += temp
    return result if result > 0 else 0


@app.get("/api/projects/{project_id}/chapters")
async def api_get_chapters(project_id: str):
    """获取项目章节列表"""
    chapters = await get_chapters(project_id)
    return {"chapters": chapters}


# ============================================================
# 剧本生成 API（核心）
# ============================================================
@app.post("/api/projects/{project_id}/generate")
async def api_generate_script(project_id: str, background_tasks: BackgroundTasks):
    """启动剧本生成（流式 SSE 返回进度）"""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.get("novel_text"):
        raise HTTPException(status_code=400, detail="请先上传小说文本")

    async def event_generator():
        """SSE 事件生成器"""
        queue = asyncio.Queue()

        async def progress_callback(stage: str, data: dict):
            await queue.put({"stage": stage, "data": data})

        # 启动生成任务
        task = asyncio.create_task(
            run_script_generation(project_id, project["novel_text"], progress_callback)
        )

        # 发送进度事件
        stages_emitted = set()
        while not task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                stage = event["stage"]
                if stage not in stages_emitted:
                    stages_emitted.add(stage)
                    yield f"data: {json.dumps({'type': 'progress', 'stage': stage, 'data': event['data']}, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                if task.done():
                    break
                continue

        # 获取结果
        result = await task
        final_yaml = result.get("final_yaml", "")

        # 保存到数据库
        if final_yaml:
            await update_project(project_id, script_yaml=final_yaml, current_stage="completed")
            await save_script_version(project_id, "v1.0", final_yaml, "AI 自动生成")

            # 保存 Agent 日志
            for log in result.get("agent_logs", []):
                await save_agent_log(
                    project_id=project_id,
                    agent_name=log.get("agent", "unknown"),
                    output_data=json.dumps(log, ensure_ascii=False),
                    status=log.get("status", "success")
                )

        yield f"data: {json.dumps({'type': 'complete', 'yaml': final_yaml, 'errors': result.get('errors', [])}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/api/projects/{project_id}/generate/status")
async def api_generation_status(project_id: str):
    """获取生成状态"""
    project = await get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {
        "current_stage": project.get("current_stage", "init"),
        "has_yaml": bool(project.get("script_yaml")),
        "agent_logs": await get_agent_logs(project_id)
    }


# ============================================================
# 剧本版本管理
# ============================================================
@app.get("/api/projects/{project_id}/versions")
async def api_get_versions(project_id: str):
    """获取剧本版本列表"""
    versions = await get_script_versions(project_id)
    return {"versions": versions}


@app.post("/api/projects/{project_id}/versions")
async def api_save_version(project_id: str, version: str = Form(...),
                            yaml_content: str = Form(...), comment: str = Form("")):
    """保存新版本"""
    result = await save_script_version(project_id, version, yaml_content, comment)
    return {"version": result}


# ============================================================
# 知识库 API
# ============================================================
@app.get("/api/knowledge/stats")
async def api_knowledge_stats():
    """获取知识库统计"""
    return await get_knowledge_stats()


@app.post("/api/knowledge/search")
async def api_knowledge_search(query: str = Form(...), top_k: int = Form(3)):
    """搜索知识库"""
    docs = await search_knowledge(query, top_k)
    return {"documents": docs}


@app.post("/api/knowledge/add")
async def api_knowledge_add(item: KnowledgeAdd):
    """添加知识"""
    doc_id = await add_knowledge(item.title, item.content, item.category)
    return {"id": doc_id, "message": "添加成功"}


# ============================================================
# 健康检查
# ============================================================
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "novel-to-script"}


# ============================================================
# 静态文件（前端构建产物）
# ============================================================
frontend_dist = Path(__file__).parent.parent / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
