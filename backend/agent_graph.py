"""LangGraph 多智能体编排 — 3 Agent 串行架构
DeconstructorAgent → ScriptAgent → AssemblyAgent（纯程序校验）
原文只传 1 次，ScriptAgent 基于完整解构数据一次性生成 YAML
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

    # DeconstructorAgent 输出
    deconstructed: str  # JSON

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

        llm = get_llm(temperature=0.2)
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

        rag_context = await retrieve_context(
            "script",
            f"剧本生成，共{len(data.get('chapters', []))}章"
        )

        llm = get_llm(temperature=0.4, max_tokens=16384)  # YAML 多章输出需要更大空间
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

        # 校验：检查是否为空
        if not yaml_text or not yaml_text.strip():
            state["errors"] = state.get("errors", []) + ["AssemblyAgent: 剧本为空"]
            state["agent_logs"] = state.get("agent_logs", []) + [{
                "agent": "AssemblyAgent", "status": "error", "error": "剧本为空"
            }]
            return state

        # 校验：检查必要字段
        required_sections = ["script:", "meta:", "characters:", "acts:"]
        missing = [s for s in required_sections if s not in yaml_text]

        warnings = []
        if missing:
            warnings.append(f"缺少字段: {', '.join(missing)}")

        # 校验：检查是否有明显编造的角色（不在角色表中的名字）
        data = _parse_deconstructed(state)
        valid_names = {c.get("name", "") for c in data.get("characters", [])}
        valid_names.add("")  # 空字符串允许

        # 查找 YAML 中 character_name 引用的名字
        char_refs = re.findall(r'character_name:\s*"([^"]*)"', yaml_text)
        char_refs += re.findall(r"character_name:\s*'([^']*)'", yaml_text)
        unknown = [n for n in char_refs if n and n not in valid_names]
        if unknown:
            warnings.append(f"引用了角色表中不存在的角色: {', '.join(set(unknown))}")

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
    """构建 3 Agent 串行工作流：
    DeconstructorAgent → ScriptAgent → AssemblyAgent
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("deconstructor_agent", deconstructor_agent)
    workflow.add_node("script_agent", script_agent)
    workflow.add_node("assembly_agent", assembly_agent)

    workflow.set_entry_point("deconstructor_agent")
    workflow.add_edge("deconstructor_agent", "script_agent")
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
        "deconstructed": "",
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
