"""数据库层 - SQLite 异步访问"""
import aiosqlite
import json
import os
from datetime import datetime
from config import settings

DB_PATH = settings.DATABASE_PATH


async def get_db() -> aiosqlite.Connection:
    """获取数据库连接"""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """初始化数据库表"""
    # 确保 data 目录存在
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(db_dir, exist_ok=True)

    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                original_work TEXT,
                original_author TEXT,
                script_type TEXT DEFAULT 'movie',
                status TEXT DEFAULT 'draft',
                novel_text TEXT,
                chapter_count INTEGER DEFAULT 0,
                script_yaml TEXT,
                intermediate_state TEXT,
                current_stage TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                analysis_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS agent_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                input_data TEXT,
                output_data TEXT,
                tokens_used INTEGER DEFAULT 0,
                duration_ms INTEGER DEFAULT 0,
                status TEXT DEFAULT 'success',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS script_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                version TEXT NOT NULL,
                yaml_content TEXT NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_chapters_project ON chapters(project_id);
            CREATE INDEX IF NOT EXISTS idx_agent_logs_project ON agent_logs(project_id);
            CREATE INDEX IF NOT EXISTS idx_script_versions_project ON script_versions(project_id);
        """)
        await db.commit()
    finally:
        await db.close()


async def create_project(project_id: str, title: str, original_work: str = "",
                         original_author: str = "", script_type: str = "movie",
                         novel_text: str = "", chapter_count: int = 0) -> dict:
    """创建新项目"""
    db = await get_db()
    try:
        now = datetime.utcnow().isoformat()
        await db.execute(
            """INSERT INTO projects (id, title, original_work, original_author, script_type,
               novel_text, chapter_count, current_stage, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'init', ?, ?)""",
            (project_id, title, original_work, original_author, script_type,
             novel_text, chapter_count, now, now)
        )
        await db.commit()
        return await get_project(project_id)
    finally:
        await db.close()


async def get_project(project_id: str) -> dict | None:
    """获取项目详情"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cursor.fetchone()
        if row:
            return dict(row)
        return None
    finally:
        await db.close()


async def list_projects() -> list[dict]:
    """列出所有项目"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def update_project(project_id: str, **kwargs) -> dict | None:
    """更新项目"""
    db = await get_db()
    try:
        kwargs["updated_at"] = datetime.utcnow().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [project_id]
        await db.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            values
        )
        await db.commit()
        return await get_project(project_id)
    finally:
        await db.close()


async def delete_project(project_id: str) -> bool:
    """删除项目"""
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def save_chapter(project_id: str, chapter_number: int, title: str,
                       content: str) -> dict:
    """保存章节"""
    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO chapters (project_id, chapter_number, title, content)
               VALUES (?, ?, ?, ?)""",
            (project_id, chapter_number, title, content)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM chapters WHERE project_id = ? AND chapter_number = ?",
            (project_id, chapter_number)
        )
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()


async def update_chapter_analysis(chapter_id: int, analysis_json: str):
    """更新章节分析结果"""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE chapters SET analysis_json = ? WHERE id = ?",
            (analysis_json, chapter_id)
        )
        await db.commit()
    finally:
        await db.close()


async def get_chapters(project_id: str) -> list[dict]:
    """获取项目的所有章节"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM chapters WHERE project_id = ? ORDER BY chapter_number",
            (project_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def save_agent_log(project_id: str, agent_name: str, input_data: str = "",
                         output_data: str = "", tokens_used: int = 0,
                         duration_ms: int = 0, status: str = "success",
                         error_message: str = "") -> dict:
    """保存 Agent 执行日志"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO agent_logs (project_id, agent_name, input_data, output_data,
               tokens_used, duration_ms, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, agent_name, input_data, output_data,
             tokens_used, duration_ms, status, error_message)
        )
        await db.commit()
        return {"id": cursor.lastrowid}
    finally:
        await db.close()


async def get_agent_logs(project_id: str) -> list[dict]:
    """获取项目的 Agent 执行日志"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM agent_logs WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


async def save_script_version(project_id: str, version: str,
                               yaml_content: str, comment: str = "") -> dict:
    """保存剧本版本"""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO script_versions (project_id, version, yaml_content, comment)
               VALUES (?, ?, ?, ?)""",
            (project_id, version, yaml_content, comment)
        )
        await db.commit()
        return {"id": cursor.lastrowid}
    finally:
        await db.close()


async def get_script_versions(project_id: str) -> list[dict]:
    """获取剧本版本历史"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM script_versions WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()
