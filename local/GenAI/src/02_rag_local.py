"""Local retrieval-augmented generation with Ollama and FAISS."""

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ollama_config import get_chat_model, get_embeddings


DEFAULT_DOCUMENTS = [
	Document(page_content="MLOps automates the lifecycle of machine learning models."),
	Document(page_content="RAG retrieves relevant context before an LLM generates an answer."),
	Document(page_content="Ollama runs open-weight language models locally through a local API."),
	Document(page_content="The project owner selected FAISS for local vector search."),
	Document(page_content="The project owner name is John Doe Jay."),
]


def build_index(documents: list[Document] | None = None) -> FAISS:
	"""Split documents and build an in-memory FAISS index."""
	source_documents = documents or DEFAULT_DOCUMENTS
	splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
	chunks = splitter.split_documents(source_documents)
	return FAISS.from_documents(chunks, get_embeddings())


def answer_question(question: str, index: FAISS | None = None) -> str:
	"""Retrieve relevant documents and ask Ollama to answer from that context."""
	vector_store = index or build_index()
	context = "\n\n".join(document.page_content for document in vector_store.similarity_search(question, k=3))
	prompt = ChatPromptTemplate.from_messages(
		[
			("system", "Answer only from the supplied context. If it is insufficient, say so."),
			("human", "Context:\n{context}\n\nQuestion: {question}"),
		]
	)
	response = (prompt | get_chat_model()).invoke({"context": context, "question": question})
	return str(response.content)


if __name__ == "__main__":
	print("RAG chat is ready. Type 'exit' or 'quit' to stop.")
	index = build_index()
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
			print(f"\nAssistant: {answer_question(question, index)}")
		except Exception as error:
			print(f"\nRequest failed: {error}")
