"""FastAPI service exposing a local Ollama question endpoint."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ollama_config import get_chat_model


app = FastAPI(title="MLOps GenAI Local API", version="0.1.0")


class QuestionRequest(BaseModel):
	question: str = Field(min_length=1, max_length=4_000)


class AnswerResponse(BaseModel):
	answer: str


@app.get("/health")
def health() -> dict[str, str]:
	return {"status": "ok"}


@app.post("/ask", response_model=AnswerResponse)
def ask(request: QuestionRequest) -> AnswerResponse:
	try:
		response = get_chat_model().invoke(request.question)
	except Exception as error:
		raise HTTPException(status_code=503, detail="Ollama is unavailable") from error
	return AnswerResponse(answer=str(response.content))


if __name__ == "__main__":
	import uvicorn

	uvicorn.run("04_api_server:app", host="127.0.0.1", port=8000, reload=False)
