"""LangGraph 多智能体编排 — 4 Agent 优化架构
DeconstructorAgent → StructureAgent + ContentAgent（并行） → AssemblyAgent（纯程序）
"""
import json
import time
import re
from typing import TypedDict, Annotated, Sequence
from operator import add

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from config import settings
from prompts import (
    DECONSTRUCTOR_AGENT_PROMPT,
    STRUCTURE_AGENT_PROMPT,
    CONTENT_AGENT_PROMPT,
    JSON_OUTPUT_RULES,
)
from rag import retrieve_context


# ============================================================
# 状态定义
# ============================================================
class AgentState(TypedDict):
    project_id: str
    novel_text: str

    # 结构化中间层（DeconstructorAgent 输出）
    deconstructed: str  # JSON: {meta, chapters, characters, settings, dialogue_excerpts}

    # StructureAgent 输出
    acts_structure: str  # JSON: {acts, adaptation_notes}

    # ContentAgent 输出
    scenes_with_beats: str  # JSON: {scenes_with_beats}

    # 最终 YAML
    final_yaml: str

    # 日志
    agent_logs: Annotated[Sequence[dict], add]
    errors: Annotated[Sequence[str], add]


# ============================================================
# LLM 工厂
# ============================================================
def get_llm(temperature: float = 0.7) -> ChatOpenAI:
    return ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=settings.LLM_MODEL,
        temperature=temperature,
    )


def extract_json_from_response(text: str) -> str:
    """从 LLM 响应中提取 JSON 内容"""
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start:brace_end + 1]
    return text.strip()


def repair_json(text: str) -> str:
    """使用 json_repair 库修复 LLM 输出中常见的 JSON 格式错误"""
    from json_repair import repair_json as _repair
    content = extract_json_from_response(text)
    try:
        return _repair(content)
    except Exception:
        return content


async def call_llm_and_parse_json(llm: ChatOpenAI, prompt: str) -> str:
    """调用 LLM 并安全解析 JSON"""
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = response.content
    content = repair_json(raw)
    try:
        json.loads(content)
    except json.JSONDecodeError:
        content = repair_json(content)
        json.loads(content)
    return content


# ============================================================
# Agent 节点实现
# ============================================================

async def deconstructor_agent(state: AgentState) -> AgentState:
    """解构 Agent — 一次性从原文提取所有结构化信息（唯一读原文的 Agent）"""
    start_time = time.time()

    try:
        rag_context = await retrieve_context(
            "deconstruct",
            f"小说解构，{state['novel_text'][:200]}..."
        )

        llm = get_llm(temperature=0.3)  # 低温度确保忠实原文
        prompt = DECONSTRUCTOR_AGENT_PROMPT.format(
            novel_text=state["novel_text"],
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)
        state["deconstructed"] = content

        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "DeconstructorAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"DeconstructorAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "DeconstructorAgent", "status": "error", "error": str(e)
        }]

    return state


def _parse_deconstructed(state: AgentState) -> dict:
    """解析解构数据，提取各子模块"""
    try:
        return json.loads(state.get("deconstructed", "{}"))
    except json.JSONDecodeError:
        return {}


async def structure_agent(state: AgentState) -> AgentState:
    """结构 Agent — 基于解构数据设计幕场骨架"""
    start_time = time.time()
    data = _parse_deconstructed(state)

    try:
        chapters_info = json.dumps({
            "chapters": data.get("chapters", []),
            "meta": data.get("meta", {})
        }, ensure_ascii=False, indent=2)
        characters_info = json.dumps(data.get("characters", []), ensure_ascii=False, indent=2)
        settings_info = json.dumps(data.get("settings", []), ensure_ascii=False, indent=2)

        rag_context = await retrieve_context(
            "structure",
            f"剧本结构设计，共{len(data.get('chapters', []))}章"
        )

        llm = get_llm(temperature=0.4)
        prompt = STRUCTURE_AGENT_PROMPT.format(
            chapters_info=chapters_info,
            characters_info=characters_info,
            settings_info=settings_info,
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)
        state["acts_structure"] = content

        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "StructureAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"StructureAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "StructureAgent", "status": "error", "error": str(e)
        }]

    return state


async def content_agent(state: AgentState) -> AgentState:
    """内容 Agent — 基于解构数据和幕场骨架，填充对白与场景内容"""
    start_time = time.time()
    data = _parse_deconstructed(state)

    try:
        acts_structure = state.get("acts_structure", "{}")
        characters_info = json.dumps(data.get("characters", []), ensure_ascii=False, indent=2)
        dialogue_excerpts = json.dumps(data.get("dialogue_excerpts", []), ensure_ascii=False, indent=2)
        settings_info = json.dumps(data.get("settings", []), ensure_ascii=False, indent=2)

        rag_context = await retrieve_context(
            "content",
            f"对白与场景内容填充，{data.get('meta', {}).get('title', '')}"
        )

        llm = get_llm(temperature=0.5)
        prompt = CONTENT_AGENT_PROMPT.format(
            acts_structure=acts_structure,
            characters_info=characters_info,
            dialogue_excerpts=dialogue_excerpts,
            settings_info=settings_info,
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)
        state["scenes_with_beats"] = content

        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "ContentAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"ContentAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "ContentAgent", "status": "error", "error": str(e)
        }]

    return state


def _escape_yaml_value(val: str) -> str:
    """安全转义 YAML 字符串值"""
    if not val:
        return "''"
    if '\n' in val:
        return f'"{val.replace(chr(92), chr(92)+chr(92)).replace(chr(34), chr(92)+chr(34))}"'
    if any(c in val for c in ':{}[]&*?|>!%@`,'):
        return f'"{val}"'
    return val


def _indent(level: int) -> str:
    return "  " * level


def _build_yaml_characters(data: dict) -> str:
    """从解构数据构建 characters YAML"""
    lines = ["characters:"]
    for ch in data.get("characters", []):
        lines.append(f"{_indent(1)}- id: {ch.get('id', '')}")
        lines.append(f"{_indent(2)}name: {_escape_yaml_value(ch.get('name', ''))}")
        lines.append(f"{_indent(2)}role_type: {ch.get('role_type', 'supporting')}")
        personality = ch.get("personality", [])
        if personality:
            lines.append(f"{_indent(2)}personality:")
            for p in personality:
                lines.append(f"{_indent(3)}- {_escape_yaml_value(p)}")
        lines.append(f"{_indent(2)}background: {_escape_yaml_value(ch.get('background', ''))}")
        lines.append(f"{_indent(2)}arc: {_escape_yaml_value(ch.get('arc', ''))}")
        relationships = ch.get("relationships", [])
        if relationships:
            lines.append(f"{_indent(2)}relationships:")
            for r in relationships:
                lines.append(f"{_indent(3)}- target_name: {_escape_yaml_value(r.get('target_name', ''))}")
                lines.append(f"{_indent(4)}relation: {_escape_yaml_value(r.get('relation', ''))}")
                lines.append(f"{_indent(4)}description: {_escape_yaml_value(r.get('description', ''))}")
    return '\n'.join(lines)


def _build_yaml_locations(data: dict) -> str:
    """从解构数据构建 locations YAML"""
    lines = ["locations:"]
    for loc in data.get("settings", []):
        lines.append(f"{_indent(1)}- id: {loc.get('id', '')}")
        lines.append(f"{_indent(2)}name: {_escape_yaml_value(loc.get('name', ''))}")
        lines.append(f"{_indent(2)}type: {loc.get('type', 'interior')}")
        lines.append(f"{_indent(2)}description: {_escape_yaml_value(loc.get('description', ''))}")
        props = loc.get("props", [])
        if props:
            lines.append(f"{_indent(2)}props:")
            for p in props:
                lines.append(f"{_indent(3)}- {_escape_yaml_value(p)}")
    return '\n'.join(lines)


def _build_yaml_acts_and_scenes(data: dict, acts_data: dict, beats_data: dict) -> str:
    """构建 acts → scenes → beats YAML"""
    lines = ["acts:"]

    # 建立 scene_number → beats 索引
    beats_map = {}
    for s in beats_data.get("scenes_with_beats", []):
        beats_map[s.get("scene_number")] = s

    for act in acts_data.get("acts", []):
        lines.append(f"{_indent(1)}- act_number: {act.get('act_number')}")
        lines.append(f"{_indent(2)}title: {_escape_yaml_value(act.get('title', ''))}")
        lines.append(f"{_indent(2)}summary: {_escape_yaml_value(act.get('summary', ''))}")
        lines.append(f"{_indent(2)}scenes:")

        for scene in act.get("scenes", []):
            sn = scene.get("scene_number")
            lines.append(f"{_indent(3)}- scene_number: {sn}")
            lines.append(f"{_indent(4)}scene_title: {_escape_yaml_value(scene.get('scene_title', ''))}")
            lines.append(f"{_indent(4)}location_id: {scene.get('location_id', '')}")
            lines.append(f"{_indent(4)}time: {scene.get('time', '日')}")
            lines.append(f"{_indent(4)}summary: {_escape_yaml_value(scene.get('summary', ''))}")

            chars = scene.get("characters_present", [])
            if chars:
                lines.append(f"{_indent(4)}characters_present:")
                for c in chars:
                    lines.append(f"{_indent(5)}- {c}")

            # 节拍
            beat_data = beats_map.get(sn, {})
            beat_list = beat_data.get("beats", [])
            if beat_list:
                lines.append(f"{_indent(4)}beats:")
                for beat in beat_list:
                    bt = beat.get("type", "action")
                    lines.append(f"{_indent(5)}- beat_number: {beat.get('beat_number')}")
                    lines.append(f"{_indent(6)}type: {bt}")
                    if beat.get("description"):
                        lines.append(f"{_indent(6)}description: {_escape_yaml_value(beat['description'])}")
                    if bt in ("dialogue", "monologue", "narration") and beat.get("character_name"):
                        lines.append(f"{_indent(6)}character_name: {_escape_yaml_value(beat['character_name'])}")
                    if beat.get("dialogue"):
                        lines.append(f"{_indent(6)}dialogue: {_escape_yaml_value(beat['dialogue'])}")
                    if beat.get("emotion"):
                        lines.append(f"{_indent(6)}emotion: {_escape_yaml_value(beat['emotion'])}")

            transition = beat_data.get("transition", "cut_to")
            lines.append(f"{_indent(4)}transition: {transition}")

    return '\n'.join(lines)


async def assembly_agent(state: AgentState) -> AgentState:
    """整合 Agent — 纯 Python 拼接 YAML，不调用 LLM"""
    start_time = time.time()

    try:
        data = _parse_deconstructed(state)

        try:
            acts_data = json.loads(state.get("acts_structure", "{}"))
        except json.JSONDecodeError:
            acts_data = {}

        try:
            beats_data = json.loads(state.get("scenes_with_beats", "{}"))
        except json.JSONDecodeError:
            beats_data = {}

        meta = data.get("meta", {})
        chapters = data.get("chapters", [])

        # 构建 YAML
        yaml_parts = ["script:"]

        # meta
        yaml_parts.append(f"{_indent(1)}meta:")
        yaml_parts.append(f"{_indent(2)}title: {_escape_yaml_value(meta.get('title', ''))}")
        yaml_parts.append(f"{_indent(2)}original_author: {_escape_yaml_value(meta.get('author') or '')}")
        yaml_parts.append(f"{_indent(2)}version: '1.0'")
        genres = meta.get("genre", [])
        if genres:
            yaml_parts.append(f"{_indent(2)}genre:")
            for g in genres:
                yaml_parts.append(f"{_indent(3)}- {_escape_yaml_value(g)}")
        yaml_parts.append(f"{_indent(2)}logline: {_escape_yaml_value(meta.get('logline', ''))}")
        yaml_parts.append(f"{_indent(2)}synopsis: {_escape_yaml_value(meta.get('logline', ''))}")
        yaml_parts.append(f"{_indent(2)}source_chapters:")
        for ch in chapters:
            yaml_parts.append(f"{_indent(3)}- chapter: {ch.get('chapter_number')}")
            yaml_parts.append(f"{_indent(4)}title: {_escape_yaml_value(ch.get('title', ''))}")

        # characters
        yaml_parts.append(_build_yaml_characters(data))

        # locations
        yaml_parts.append(_build_yaml_locations(data))

        # acts
        yaml_parts.append(_build_yaml_acts_and_scenes(data, acts_data, beats_data))

        # notes
        adaptation = acts_data.get("adaptation_notes", {})
        yaml_parts.append("notes:")
        mapping = adaptation.get("chapters_to_acts_mapping", "")
        yaml_parts.append(f"{_indent(1)}adaptation_notes: {_escape_yaml_value(mapping)}")
        pacing = adaptation.get("pacing_suggestions", "")
        if pacing:
            yaml_parts.append(f"{_indent(1)}director_notes: {_escape_yaml_value(pacing)}")

        state["final_yaml"] = '\n'.join(yaml_parts)
        dur = int((time.time() - start_time) * 1000)

        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "AssemblyAgent",
            "status": "success",
            "duration_ms": dur,
            "output_preview": state["final_yaml"][:300] + "..."
        }]

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
    """构建 4 Agent 工作流：
    DeconstructorAgent → StructureAgent + ContentAgent（并行） → AssemblyAgent
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("deconstructor_agent", deconstructor_agent)
    workflow.add_node("structure_agent", structure_agent)
    workflow.add_node("content_agent", content_agent)
    workflow.add_node("assembly_agent", assembly_agent)

    workflow.set_entry_point("deconstructor_agent")

    # DeconstructorAgent 完成后，StructureAgent 和 ContentAgent 并行执行
    workflow.add_edge("deconstructor_agent", "structure_agent")
    workflow.add_edge("deconstructor_agent", "content_agent")

    # 两者都完成后，AssemblyAgent 整合
    workflow.add_edge("structure_agent", "assembly_agent")
    workflow.add_edge("content_agent", "assembly_agent")

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
        "deconstructed": "",
        "acts_structure": "",
        "scenes_with_beats": "",
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
        "acts_structure": final_state.get("acts_structure", ""),
        "scenes_with_beats": final_state.get("scenes_with_beats", ""),
    }
