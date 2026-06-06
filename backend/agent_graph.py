"""LangGraph 多智能体编排 - 小说转剧本核心引擎"""
import json
import time
import re
from typing import TypedDict, Annotated, Sequence, Literal
from operator import add

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from config import settings
from prompts import (
    CHAPTER_AGENT_PROMPT,
    CHARACTER_AGENT_PROMPT,
    PLOT_AGENT_PROMPT,
    DIALOGUE_AGENT_PROMPT,
    SCENE_AGENT_PROMPT,
    ASSEMBLY_AGENT_PROMPT,
    JSON_OUTPUT_RULES,
)
from rag import retrieve_context


# ============================================================
# 状态定义
# ============================================================
class AgentState(TypedDict):
    project_id: str
    novel_text: str
    stage: str  # 当前阶段
    stage_order: list  # 阶段顺序
    current_stage_index: int

    # 各 Agent 输出
    chapter_analysis: str
    character_analysis: str
    plot_structure: str
    dialogue_content: str
    scene_design: str
    final_yaml: str

    # 日志
    agent_logs: Annotated[Sequence[dict], add]
    errors: Annotated[Sequence[str], add]


# ============================================================
# LLM 工厂
# ============================================================
def get_llm(temperature: float = 0.7, use_small: bool = False) -> ChatOpenAI:
    model = settings.LLM_SMALL_MODEL if use_small else settings.LLM_MODEL
    return ChatOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        model=model,
        temperature=temperature,
    )


def extract_json_from_response(text: str) -> str:
    """从 LLM 响应中提取 JSON 内容"""
    # 尝试匹配 JSON 代码块
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    # 尝试匹配裸 JSON 对象
    brace_start = text.find('{')
    brace_end = text.rfind('}')
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start:brace_end + 1]

    return text.strip()


def repair_json(text: str) -> str:
    """使用 json_repair 库修复 LLM 输出中常见的 JSON 格式错误（不调 LLM，纯文本修复）"""
    from json_repair import repair_json as _repair

    # 先提取 JSON 部分
    content = extract_json_from_response(text)
    try:
        return _repair(content)
    except Exception:
        # 修复失败，返回原文
        return content


async def call_llm_and_parse_json(
    llm: ChatOpenAI,
    prompt: str,
) -> str:
    """调用 LLM 并安全解析 JSON，失败时用 json_repair 自动修复"""
    import json as json_module

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    raw = response.content

    # 用 json_repair 修复并解析
    content = repair_json(raw)

    # 验证最终结果
    try:
        json_module.loads(content)
    except json_module.JSONDecodeError:
        # 极少数情况仍失败，再试一次修复
        content = repair_json(content)
        json_module.loads(content)  # 还失败就抛异常

    return content


# ============================================================
# Agent 节点实现
# ============================================================

async def chapter_agent(state: AgentState) -> AgentState:
    """章节解析 Agent"""
    start_time = time.time()
    stage = "chapter_analysis"

    try:
        rag_context = await retrieve_context(
            stage, f"小说章节解析，共{state['novel_text'][:200]}..."
        )

        llm = get_llm(temperature=0.5)
        prompt = CHAPTER_AGENT_PROMPT.format(
            novel_text=state["novel_text"],
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)

        state["chapter_analysis"] = content
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "ChapterAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"ChapterAgent: {str(e)}"]
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "ChapterAgent",
            "status": "error",
            "error": str(e)
        }]

    return state


async def character_agent(state: AgentState) -> AgentState:
    """角色提取 Agent"""
    start_time = time.time()
    stage = "character_analysis"

    try:
        rag_context = await retrieve_context(
            stage,
            f"角色提取，章节概要：{state.get('chapter_analysis', '')[:200]}"
        )

        llm = get_llm(temperature=0.6)
        prompt = CHARACTER_AGENT_PROMPT.format(
            novel_text=state["novel_text"],
            chapter_analysis=state.get("chapter_analysis", "暂无章节分析"),
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)

        state["character_analysis"] = content
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "CharacterAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"CharacterAgent: {str(e)}"]

    return state


async def plot_agent(state: AgentState) -> AgentState:
    """情节重构 Agent"""
    start_time = time.time()
    stage = "plot_structure"

    try:
        rag_context = await retrieve_context(
            stage,
            f"情节重构，{state.get('chapter_analysis', '')[:200]}"
        )

        llm = get_llm(temperature=0.7)
        prompt = PLOT_AGENT_PROMPT.format(
            chapter_analysis=state.get("chapter_analysis", "暂无"),
            character_analysis=state.get("character_analysis", "暂无"),
            novel_text=state["novel_text"],
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)

        state["plot_structure"] = content
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "PlotAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"PlotAgent: {str(e)}"]

    return state


async def dialogue_agent(state: AgentState) -> AgentState:
    """对白生成 Agent"""
    start_time = time.time()
    stage = "dialogue_generation"

    try:
        rag_context = await retrieve_context(
            stage,
            f"对白生成，{state.get('plot_structure', '')[:200]}"
        )

        llm = get_llm(temperature=0.8)  # 对白需要更多创意
        prompt = DIALOGUE_AGENT_PROMPT.format(
            plot_structure=state.get("plot_structure", "暂无"),
            character_analysis=state.get("character_analysis", "暂无"),
            novel_text=state["novel_text"],
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)

        state["dialogue_content"] = content
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "DialogueAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"DialogueAgent: {str(e)}"]

    return state


async def scene_agent(state: AgentState) -> AgentState:
    """场景描述 Agent"""
    start_time = time.time()
    stage = "scene_design"

    try:
        rag_context = await retrieve_context(
            stage,
            f"场景设计，{state.get('plot_structure', '')[:200]}"
        )

        llm = get_llm(temperature=0.6)
        prompt = SCENE_AGENT_PROMPT.format(
            plot_structure=state.get("plot_structure", "暂无"),
            dialogue_content=state.get("dialogue_content", "暂无"),
            rag_context=rag_context,
            json_rules=JSON_OUTPUT_RULES
        )

        content = await call_llm_and_parse_json(llm, prompt)

        state["scene_design"] = content
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "SceneAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:200] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"SceneAgent: {str(e)}"]

    return state


async def assembly_agent(state: AgentState) -> AgentState:
    """整合输出 Agent"""
    start_time = time.time()

    try:
        llm = get_llm(temperature=0.3, use_small=False)  # 整合用大模型确保质量
        prompt = ASSEMBLY_AGENT_PROMPT.format(
            chapter_analysis=state.get("chapter_analysis", "暂无"),
            character_analysis=state.get("character_analysis", "暂无"),
            plot_structure=state.get("plot_structure", "暂无"),
            dialogue_content=state.get("dialogue_content", "暂无"),
            scene_design=state.get("scene_design", "暂无"),
            novel_text=state["novel_text"]
        )

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()

        # 清理可能的代码块标记
        content = re.sub(r'^```yaml\s*\n?', '', content)
        content = re.sub(r'\n?```\s*$', '', content)

        state["final_yaml"] = content
        state["agent_logs"] = state.get("agent_logs", []) + [{
            "agent": "AssemblyAgent",
            "status": "success",
            "duration_ms": int((time.time() - start_time) * 1000),
            "output_preview": content[:300] + "..."
        }]

    except Exception as e:
        state["errors"] = state.get("errors", []) + [f"AssemblyAgent: {str(e)}"]

    return state


# ============================================================
# 路由函数：决定下一步
# ============================================================
STAGE_ORDER = [
    "chapter_analysis",
    "character_analysis",
    "plot_structure",
    "dialogue_generation",
    "scene_design",
    "assembly",
    "finish"
]


def supervisor_router(state: AgentState) -> str:
    """Supervisor 路由：根据当前阶段决定下一步"""
    current = state.get("stage", "chapter_analysis")

    try:
        idx = STAGE_ORDER.index(current)
        next_stage = STAGE_ORDER[idx + 1]
    except (ValueError, IndexError):
        return END

    # 更新阶段
    state["stage"] = next_stage

    # 路由到对应节点
    stage_to_node = {
        "chapter_analysis": "chapter_agent",
        "character_analysis": "character_agent",
        "plot_structure": "plot_structure",
        "dialogue_generation": "dialogue_agent",
        "scene_design": "scene_agent",
        "assembly": "assembly_agent",
        "finish": END,
    }

    return stage_to_node.get(next_stage, END)


# ============================================================
# 构建 Graph
# ============================================================
def build_script_graph() -> StateGraph:
    """构建小说转剧本的 LangGraph 工作流"""
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("chapter_agent", chapter_agent)
    workflow.add_node("character_agent", character_agent)
    workflow.add_node("plot_agent", plot_agent)
    workflow.add_node("dialogue_agent", dialogue_agent)
    workflow.add_node("scene_agent", scene_agent)
    workflow.add_node("assembly_agent", assembly_agent)

    # 设置入口
    workflow.set_entry_point("chapter_agent")

    # 设置边（顺序执行）
    workflow.add_edge("chapter_agent", "character_agent")
    workflow.add_edge("character_agent", "plot_agent")
    workflow.add_edge("plot_agent", "dialogue_agent")
    workflow.add_edge("dialogue_agent", "scene_agent")
    workflow.add_edge("scene_agent", "assembly_agent")
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
    """
    执行完整的剧本生成流程

    Args:
        project_id: 项目ID
        novel_text: 小说原文
        event_callback: 可选，用于流式推送中间状态的回调函数
            async def callback(stage: str, data: dict)

    Returns:
        包含 final_yaml 和 agent_logs 的字典
    """
    graph = build_script_graph()

    initial_state: AgentState = {
        "project_id": project_id,
        "novel_text": novel_text,
        "stage": "start",
        "stage_order": STAGE_ORDER,
        "current_stage_index": 0,
        "chapter_analysis": "",
        "character_analysis": "",
        "plot_structure": "",
        "dialogue_content": "",
        "scene_design": "",
        "final_yaml": "",
        "agent_logs": [],
        "errors": [],
    }

    # 流式执行，每个节点完成后推送状态
    final_state = None
    async for event in graph.astream(initial_state):
        for node_name, node_state in event.items():
            final_state = node_state

            # 推送事件
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
        "chapter_analysis": final_state.get("chapter_analysis", ""),
        "character_analysis": final_state.get("character_analysis", ""),
        "plot_structure": final_state.get("plot_structure", ""),
        "dialogue_content": final_state.get("dialogue_content", ""),
        "scene_design": final_state.get("scene_design", ""),
    }
