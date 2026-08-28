# Local Ollama Development

This folder contains the local MLOps and GenAI examples. The local workflow uses Ollama for free, locally hosted models, FAISS for local vector search, and Python 3.14 in the project `.venv`.

## Setup

From the project root in PowerShell:

```powershell
cd E:\Projects\mlops-genai-project
. .\.venv\Scripts\Activate.ps1
```

If PowerShell says that running scripts is disabled, use the temporary policy for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\.venv\Scripts\Activate.ps1
```

Verify the environment and install the Python packages:

```powershell
python --version
python -m pip install -r local/requirements.txt
```

## Ollama Models

Ollama is a separate Windows application. The Python package `ollama` is only a client that communicates with the Ollama server; it does not install the server or AI models.

Install Ollama from https://ollama.com/download/windows, then open a new PowerShell window and verify it:

```powershell
ollama --version
```

Pull the lightweight chat model and the embedding model:

```powershell
ollama pull llama3.2:1b
ollama pull nomic-embed-text
ollama list
```

If Ollama is not already running, start it in a separate PowerShell window and leave that window open:

```powershell
ollama serve
```

Configure this project to use the lightweight model:

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_CHAT_MODEL = "llama3.2:1b"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
```

## How the Local Flow Works

The Python code does not run the AI model directly. It sends a request through LangChain or LangGraph to the Ollama server. Ollama then passes the request to the downloaded `llama3.2:1b` model and returns the answer.

```text
Python application -> LangChain/LangGraph -> Ollama server
							   |
							   v
						   llama3.2:1b
							   |
							   v
						   answer to Python
```

The RAG flow is slightly different:

```text
Documents -> nomic-embed-text -> FAISS vector search
Question  -> nomic-embed-text -> relevant document chunks
Question plus context -> Ollama -> llama3.2:1b -> answer
```

FAISS is free and runs locally. It does not require a cloud database or AWS account.

## Direct Chat vs RAG

The direct chat script, `01_langchain_local.py`, sends the question straight to the chat model:

```text
Question -> Ollama -> llama3.2:1b -> answer
```

The RAG script, `02_rag_local.py`, searches the local FAISS index first. It then sends the question and the retrieved document context to Ollama:

```text
Question -> nomic-embed-text -> FAISS search -> relevant context
Question plus context -> Ollama -> llama3.2:1b -> answer
```

FAISS finds the relevant information; it does not write the answer. Ollama generates the final response using the retrieved context.

Both scripts may produce similar answers for general questions because `llama3.2:1b` already knows common topics. RAG becomes useful when the answer depends on private or project-specific documents that were added to the index.

## Local Python Files

- `GenAI/src/ollama_config.py`: Shared Ollama URL, chat model, embedding model, and LangChain factory functions.
- `GenAI/src/01_langchain_local.py`: Sends a simple question to `llama3.2:1b` through LangChain.
- `GenAI/src/02_rag_local.py`: Embeds documents with `nomic-embed-text`, searches them with FAISS, and asks Ollama for a context-based answer.
- `GenAI/src/03_langgraph_local.py`: Runs a small stateful LangGraph workflow with Ollama.
- `Predictive ML/src/01_model_training.py`: Trains a local scikit-learn classifier and saves `artifacts/iris_model.joblib`.
- `Predictive ML/src/02_drift_detection.py`: Calculates Population Stability Index and reports stable, warning, or alert status.
- `GenAI/src/04_api_server.py`: Exposes `/health` and `/ask` through FastAPI; `/ask` sends questions to Ollama.

## Test the Local Workflow

Run the non-Ollama examples first:

```powershell
python "local/Predictive ML/src/01_model_training.py"
python "local/Predictive ML/src/02_drift_detection.py"
```

Then test the Ollama chat and RAG examples:

```powershell
python "local/GenAI/src/01_langchain_local.py"
python "local/GenAI/src/02_rag_local.py"
python "local/GenAI/src/03_langgraph_local.py"
```

Run the automated test suite:

```powershell
python -m pytest
```

Start the API from the `local/GenAI` directory:

```powershell
cd local/GenAI/src
uvicorn 04_api_server:app --host 127.0.0.1 --port 8000
```

From another PowerShell window, check the API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask -ContentType "application/json" -Body '{"question":"What is MLOps?"}'
```

## Troubleshooting

### `ollama` is not recognized

Install the Ollama Windows application and open a new PowerShell window so the command is added to `PATH`.

### Connection refused at port `11434`

Start the local server:

```powershell
ollama serve
```

### Model not found

Check installed models and pull them again if necessary:

```powershell
ollama list
ollama pull llama3.2:1b
ollama pull nomic-embed-text
```
