"""Minimal LangChain chat example backed by a local Ollama model."""

from ollama_config import get_chat_model


def ask(question: str) -> str:
	"""Send one question to Ollama and return the model response."""
	response = get_chat_model().invoke(question)
	return str(response.content)


if __name__ == "__main__":
	print("Ollama chat is ready. Type 'exit' or 'quit' to stop.")
	while True:
		try:
			question = input("\nYou: ").strip()
		except (EOFError, KeyboardInterrupt):
			print("\nGoodbye!")
			break

		if question.lower() in {"exit", "quit"}:
			print("Goodbye!")
			break
		if not question:
			continue

		try:
			print(f"\nAssistant: {ask(question)}")
		except Exception as error:
			print(f"\nRequest failed: {error}")
