"""Simple stateful LangGraph workflow using a local Ollama model."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ollama_config import get_chat_model


class GraphState(TypedDict):
	question: str
	answer: str


def generate_answer(state: GraphState) -> dict[str, str]:
	"""Generate an answer for the current graph state."""
	response = get_chat_model().invoke(state["question"])
	return {"answer": str(response.content)}


def build_graph():
	"""Compile the local question-answer graph."""
	workflow = StateGraph(GraphState)
	workflow.add_node("generate_answer", generate_answer)
	workflow.add_edge(START, "generate_answer")
	workflow.add_edge("generate_answer", END)
	return workflow.compile()


if __name__ == "__main__":
	result = build_graph().invoke({"question": "What does a model pipeline automate?", "answer": ""})
	print(result["answer"])
