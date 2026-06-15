from langgraph.graph import StateGraph, END
from pipeline.state import AgentState
from pipeline.agents.code_reader import code_reader
from pipeline.agents.planner     import planner
from pipeline.agents.code_writer import code_writer
from pipeline.agents.sandbox     import sandbox
from pipeline.agents.pr_opener   import pr_opener

# critic agent is not yet implemented — will be wired in next phase


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("code_reader", code_reader)
    graph.add_node("planner",     planner)
    graph.add_node("code_writer", code_writer)
    graph.add_node("sandbox",     sandbox)
    graph.add_node("pr_opener",   pr_opener)

    graph.set_entry_point("code_reader")
    graph.add_edge("code_reader", "planner")
    graph.add_edge("planner",     "code_writer")
    graph.add_edge("code_writer", "sandbox")
    graph.add_edge("sandbox",     "pr_opener")

    graph.add_edge("pr_opener", END)
    return graph.compile()