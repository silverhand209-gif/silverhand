"""LangGraph 多智能体编排 — 3 Agent 串行架构（支持分章批处理）
DeconstructorAgent（逐章循环）→ OverviewAgent → ScriptAgent → AssemblyAgent（纯程序校验）
每章独立解构后增量累积，支持无限章节扩展
"""
import json
import time
import re
from typing import TypedDict, Annotated, Sequence, List
from operator import add

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from prompts import (
    CHAPTER_DECONSTRUCT_PROMPT,
    OVERVIEW_PROMPT,
    SCRIPT_AGENT_PROMPT,
    JSON_OUTPUT_RULES,
)
from rag import retrieve_context


# ============================================================
# 状态定义
# ============================================================
class AgentState(TypedDict):
    project_id: str
    novel_text: str

    # 分章数据
    chapters_raw: list  # [{number, title, text}, ...]

    # DeconstructorAgent 累积输出
    deconstructed: str  # JSON

    # OverviewAgent 输出
    overview: str  # JSON

    # ScriptAgent 输出
    final_yaml: str

    # 日志
    agent_logs: Annotated[Sequence[dict], add]
    errors: Annotated[Sequence[str], add]


# ============================================================
# LLM 工厂
# ============================================================
def get_llm(temperature: float = 0.7, max_tokens: int = 4096) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def extract_json_from_response(text: str) -> str:
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start:brace_end + 1]
    return text.strip()


def repair_json(text: str) -> str:
    from json_repair import repair_json as _repair
    content = extract_json_from_response(text)
    try:
        return _repair(content)
    except Exception:
        return content


async def call_llm_and_parse_json(llm: ChatOpenAI, prompt: str) -> str:
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = response.content
    content = repair_json(raw)
    try:
        json.loads(content)
    except json.JSONDecodeError:
        content = repair_json(content)
        json.loads(content)
    return content


def _parse_deconstructed(state: AgentState) -> dict:
    try:
        return json.loads(state.get("deconstructed", "{}"))
    except json.JSONDecodeError:
        return {}


def _parse_overview(state: AgentState) -> dict:
    try:
        return json.loads(state.get("overview", "{}"))
    except json.JSONDecodeError:
        return {}


# ============================================================
# 章节分割工具
# ============================================================
CHAPTER_PATTERN = re.compile(
    r'(?:第\s*([一二三四五六七八九十百千万零\d]+)\s*章\s*[^\n]*)'
)


def split_chapters(novel_text: str) -> List[dict]:
    """将小说文本按章节标题分割，返回 [{number, title, text}, ...]"""
    splits = list(CHAPTER_PATTERN.finditer(novel_text))
    if len(splits) < 2:
        # 无法分割，整体作为一章
        return [{"number": 1, "title": "全文", "text": novel_text}]

    chapters = []
    for i, match in enumerate(splits):
        title = match.group(0).strip()
        start = match.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(novel_text)
        text = novel_text[start:end].strip()
        num_str = match.group(1)
        try:
            num = int(num_str)
        except ValueError:
            num = _cn_num_to_int(num_str)
        chapters.append({"number": num, "title": title, "text": text})
    return chapters


def _cn_num_to_int(cn: str) -> int:
    """中文数字转阿拉伯数字"""
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


# ============================================================
# Agent 节点实现
# ============================================================

async def deconstructor_agent(state: AgentState) -> AgentState:
    """解构 Agent — 逐章循环处理，增量累积结构化数据"""
    start_time = time.time()
    chapters = state.get("chapters_raw", [])
    if not chapters:
        chapters = split_chapters(state["novel_text"])
        state["chapters_raw"] = chapters

    total = len(chapters)

    # 累积容器
    all_chapters_info = []
    all_characters = {}  # name -> char_data (去重合并)
    all_settings = {}    # name -> setting_data
    all_plot_events = []  # 全局有序事件列表
    all_dialogues = []
    global_order = 0
    char_id_counter = [0]
    loc_id_counter = [0]

    try:
        llm = get_llm(temperature=0.2, max_tokens=4096)  # 单章输出，4096 足够

        for idx, ch in enumerate(chapters):
            ch_num = ch["number"]
            ch_title = ch["title"]
            ch_text = ch["text"]

            prompt = CHAPTER_DECONSTRUCT_PROMPT.format(
                chapter_number=ch_num,
                chapter_title=ch_title,
                chapter_text=ch_text,
                json_rules=JSON_OUTPUT_RULES,
            )

            content = await call_llm_and_parse_json(llm, prompt)
            data = json.loads(content)

            # 累积章节信息
            all_chapters_info.append({
                "chapter_number": ch_num,
                "title": ch_title,
                "summary": data.get("summary", ""),
                "key_events": data.get("key_events", []),
                "characters_appeared": [c.get("name", "") for c in data.get("new_characters", [])],
                "locations": [s.get("name", "") for s in data.get("new_settings", [])],
            })

            # 累积角色（按 name 去重合并）
            for c in data.get("new_characters", []):
                name = c.get("name", "")
                if name and name not in all_characters:
                    char_id_counter[0] += 1
                    all_characters[name] = {
                        "id": f"char_{char_id_counter[0]:03d}",
                        "name": name,
                        "aliases": c.get("aliases", []),
                        "role_type": c.get("role_type", "supporting"),
                        "personality": c.get("personality", []),
                        "background": c.get("background", ""),
                        "dialogue_style": c.get("dialogue_style", ""),
                        "dialogue_samples": c.get("dialogue_samples", []),
                        "first_appearance_chapter": ch_num,
                    }
                elif name:
                    # 合并性格和背景
                    existing = all_characters[name]
                    existing["personality"] = list(set(existing.get("personality", []) + c.get("personality", [])))
                    if c.get("background"):
                        existing["background"] = existing.get("background", "") + "; " + c.get("background", "")

            # 累积场景（按 name 去重）
            for s in data.get("new_settings", []):
                sname = s.get("name", "")
                if sname and sname not in all_settings:
                    loc_id_counter[0] += 1
                    all_settings[sname] = {
                        "id": f"loc_{loc_id_counter[0]:03d}",
                        "name": sname,
                        "type": s.get("type", "interior"),
                        "description": s.get("description", ""),
                        "appears_in_chapters": [ch_num],
                    }
                elif sname:
                    all_settings[sname]["appears_in_chapters"].append(ch_num)

            # 累积情节事件
            for ev in data.get("plot_events", []):
                global_order += 1
                all_plot_events.append({
                    "order": global_order,
                    "chapter": ch_num,
                    "event": ev.get("event", ""),
                    "characters_involved": ev.get("characters_involved", []),
                    "location": ev.get("location", ""),
                    "source_text": ev.get("source_text", ""),
                })

            # 累积对话
            for d in data.get("dialogues", []):
                all_dialogues.append({
                    "chapter": ch_num,
                    "speaker": d.get("speaker", ""),
                    "line": d.get("line", ""),
                })

            state["agent_logs"] = state.get("agent_logs", []) + [{
                "agent": "DeconstructorAgent",
                "status": "progress",
                "message": f"第{ch_num}章解构完成 ({idx+1}/{total})",
                "dialogues_found": len(data.get("dialogues", [])),
            }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"DeconstructorAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "DeconstructorAgent", "status": "error", "error": str(e)
        }]
        return state

    # 汇总
    deconstructed = json.dumps({
        "chapters": all_chapters_info,
        "characters": list(all_characters.values()),
        "settings": list(all_settings.values()),
        "plot_timeline": all_plot_events,
        "all_dialogues": all_dialogues,
    }, ensure_ascii=False)

    state["deconstructed"] = deconstructed

    state["agent_logs"] = state.get("agent_logs", []) + [{
        "agent": "DeconstructorAgent",
        "status": "success",
        "duration_ms": int((time.time() - start_time) * 1000),
        "summary": f"共处理{total}章，提取角色{len(all_characters)}个，场景{len(all_settings)}个，对白{len(all_dialogues)}句，事件{len(all_plot_events)}个",
    }]

    return state


async def overview_agent(state: AgentState) -> AgentState:
    """全局概述 Agent — 基于各章摘要生成角色关系、场景综合描述"""
    start_time = time.time()
    data = _parse_deconstructed(state)

    try:
        chapters = data.get("chapters", [])
        if not chapters:
            state["overview"] = json.dumps({"meta": {}, "global_characters": [], "global_settings": []}, ensure_ascii=False)
            return state

        # 构建各章摘要文本
        chapters_summary = "\n".join([
            f"第{c.get('chapter_number', '?')}章 {c.get('title', '')}: {c.get('summary', '')}"
            for c in chapters
        ])

        llm = get_llm(temperature=0.3, max_tokens=4096)
        prompt = OVERVIEW_PROMPT.format(
            chapters_summary=chapters_summary,
            json_rules=JSON_OUTPUT_RULES,
        )

        content = await call_llm_and_parse_json(llm, prompt)
        overview_data = json.loads(content)

        # 合并 overview 的角色信息到 deconstructed 中
        global_chars = overview_data.get("global_characters", [])
        global_settings = overview_data.get("global_settings", [])

        # 用 overview 的角色信息增强已有角色数据
        existing_chars = {c.get("name", ""): c for c in data.get("characters", [])}
        for gc in global_chars:
            name = gc.get("name", "")
            if name in existing_chars:
                ec = existing_chars[name]
                # 补充 overview 分析出的额外信息
                if gc.get("arc") and not ec.get("arc"):
                    ec["arc"] = gc["arc"]
                if gc.get("relationships"):
                    ec["relationships"] = gc["relationships"]

        # 用 overview 的场景描述增强已有场景
        existing_settings = {s.get("name", ""): s for s in data.get("settings", [])}
        for gs in global_settings:
            name = gs.get("name", "")
            if name in existing_settings and gs.get("description"):
                es = existing_settings[name]
                if len(gs.get("description", "")) > len(es.get("description", "")):
                    es["description"] = gs["description"]

        # 更新 deconstructed
        deconstructed_data = _parse_deconstructed(state)
        deconstructed_data["meta"] = overview_data.get("meta", {})
        deconstructed_data["characters"] = list(existing_chars.values())
        deconstructed_data["settings"] = list(existing_settings.values())
        state["deconstructed"] = json.dumps(deconstructed_data, ensure_ascii=False)
        state["overview"] = json.dumps(overview_data, ensure_ascii=False)

        dur = int((time.time() - start_time) * 1000)
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "OverviewAgent",
            "status": "success",
            "duration_ms": dur,
            "output_preview": f"全局角色{len(global_chars)}个，场景{len(global_settings)}个",
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"OverviewAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "OverviewAgent", "status": "error", "error": str(e)
        }]

    return state


async def script_agent(state: AgentState) -> AgentState:
    """剧本生成 Agent — 基于完整解构数据一次性生成 YAML 剧本"""
    start_time = time.time()
    data = _parse_deconstructed(state)

    try:
        chapters_info = json.dumps(data.get("chapters", []), ensure_ascii=False, indent=2)
        characters_info = json.dumps(data.get("characters", []), ensure_ascii=False, indent=2)
        settings_info = json.dumps(data.get("settings", []), ensure_ascii=False, indent=2)
        plot_timeline = json.dumps(data.get("plot_timeline", []), ensure_ascii=False, indent=2)
        all_dialogues = json.dumps(data.get("all_dialogues", []), ensure_ascii=False, indent=2)

        chapter_count = len(data.get("chapters", []))
        dialogue_count = len(data.get("all_dialogues", []))

        rag_context = await retrieve_context(
            "script",
            f"剧本生成，共{chapter_count}章，{dialogue_count}句对白"
        )

        # 根据章节数动态调整 max_tokens
        token_budget = max(16384, chapter_count * 2048)
        llm = get_llm(temperature=0.4, max_tokens=token_budget)
        prompt = SCRIPT_AGENT_PROMPT.format(
            chapters_info=chapters_info,
            characters_info=characters_info,
            settings_info=settings_info,
            plot_timeline=plot_timeline,
            all_dialogues=all_dialogues,
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # 清理代码块标记
        content = re.sub(r'^```ya?ml\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

        # 将 YAML 字符串值中未被解析的 \n 字面量替换为空格
        def _replace_literal_newlines_in_yaml(text: str) -> str:
            result = []
            i = 0
            in_double_quote = False
            while i < len(text):
                if text[i] == '"' and (i == 0 or text[i-1] != '\\'):
                    in_double_quote = not in_double_quote
                    result.append(text[i])
                    i += 1
                elif in_double_quote and i + 1 < len(text) and text[i:i+2] == '\\n':
                    result.append(' ')
                    i += 2
                else:
                    result.append(text[i])
                    i += 1
            return ''.join(result)

        content = _replace_literal_newlines_in_yaml(content)

        state["final_yaml"] = content

        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "ScriptAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:300] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"ScriptAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "ScriptAgent", "status": "error", "error": str(e)
        }]

    return state


async def assembly_agent(state: AgentState) -> AgentState:
    """整合校验 Agent — 纯程序校验 YAML 完整性，不调用 LLM"""
    start_time = time.time()

    try:
        yaml_text = state.get("final_yaml", "")

        if not yaml_text or not yaml_text.strip():
            state["errors"] = state.get("errors", []) + ["AssemblyAgent: 剧本为空"]
            state["agent_logs"] = state.get("agent_logs", []) + [{
                "agent": "AssemblyAgent", "status": "error", "error": "剧本为空"
            }]
            return state

        # 校验必要字段
        required_sections = ["script:", "meta:", "characters:", "acts:"]
        missing = [s for s in required_sections if s not in yaml_text]

        warnings = []
        if missing:
            warnings.append(f"缺少字段: {', '.join(missing)}")

        # 校验角色引用合法性
        data = _parse_deconstructed(state)
        valid_names = {c.get("name", "") for c in data.get("characters", [])}
        valid_names.add("")

        char_refs = re.findall(r'character_name:\s*"([^"]*)"', yaml_text)
        char_refs += re.findall(r"character_name:\s*'([^']*)'", yaml_text)
        unknown = [n for n in char_refs if n and n not in valid_names]
        if unknown:
            warnings.append(f"引用了角色表中不存在的角色: {', '.join(set(unknown))}")

        # 校验对白数量
        all_dialogues = data.get("all_dialogues", [])
        dialogue_beats = len(re.findall(r'type:\s*"dialogue"', yaml_text))
        if dialogue_beats < len(all_dialogues):
            warnings.append(f"对白缺失: all_dialogues有{len(all_dialogues)}句，剧本中仅{dialogue_beats}个dialogue beat")

        dur = int((time.time() - start_time) * 1000)
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "AssemblyAgent",
            "status": "success",
            "duration_ms": dur,
            "warnings": warnings,
            "output_preview": "校验通过" if not warnings else f"校验完成，{len(warnings)} 个警告"
        }]

        if warnings:
            state["errors"] = state.get("errors", []) + [f"AssemblyAgent: {'; '.join(warnings)}"]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"AssemblyAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "AssemblyAgent", "status": "error", "error": str(e)
        }]

    return state


# ============================================================
# 构建 Graph
# ============================================================
def build_script_graph() -> StateGraph:
    """构建 4 节点串行工作流：
    DeconstructorAgent（逐章循环）→ OverviewAgent → ScriptAgent → AssemblyAgent
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("deconstructor_agent", deconstructor_agent)
    workflow.add_node("overview_agent", overview_agent)
    workflow.add_node("script_agent", script_agent)
    workflow.add_node("assembly_agent", assembly_agent)

    workflow.set_entry_point("deconstructor_agent")
    workflow.add_edge("deconstructor_agent", "overview_agent")
    workflow.add_edge("overview_agent", "script_agent")
    workflow.add_edge("script_agent", "assembly_agent")
    workflow.add_edge("assembly_agent", END)

    return workflow.compile()


# ============================================================
# 执行入口
# ============================================================
async def run_script_generation(
    project_id: str,
    novel_text: str,
    event_callback=None
) -> dict:
    """执行完整的剧本生成流程"""
    graph = build_script_graph()

    initial_state: AgentState = {
        "project_id": project_id,
        "novel_text": novel_text,
        "chapters_raw": [],
        "deconstructed": "",
        "overview": "",
        "final_yaml": "",
        "agent_logs": [],
        "errors": [],
    }

    final_state = None
    async for event in graph.astream(initial_state):
        for node_name, node_state in event.items():
            final_state = node_state
            if event_callback:
                await event_callback(node_name, {
                    "stage": node_name,
                    "agent_logs": node_state.get("agent_logs", []),
                    "errors": node_state.get("errors", []),
                })

    if final_state is None:
        return {"final_yaml": "", "agent_logs": [], "errors": ["Graph execution failed"]}

    return {
        "final_yaml": final_state.get("final_yaml", ""),
        "agent_logs": final_state.get("agent_logs", []),
        "errors": final_state.get("errors", []),
        "deconstructed": final_state.get("deconstructed", ""),
    }
