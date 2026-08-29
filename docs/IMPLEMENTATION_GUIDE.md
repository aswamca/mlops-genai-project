# MLOps GenAI Implementation Guide

This guide explains how the local implementation is organized, what each Python file does, and why each dependency is installed. The local path uses Ollama for free, locally hosted chat and embedding models. It does not require AWS credentials for the local examples.

## Current Implementation

The local workflow has these layers:

```text
Ollama models
    |
    +-- ChatOllama -> LangChain and LangGraph examples
    |
    `-- OllamaEmbeddings -> FAISS vector search -> RAG answer

scikit-learn -> local model training -> joblib artifact
NumPy       -> drift calculations
FastAPI     -> HTTP API -> Ollama chat model
```

The files under `local/GenAI_ollama` and `local/Predictive ML` are executable examples. The Docker, Kubernetes, Terraform, test, and root dependency files are currently scaffolding for later phases.

## Before Running the Code

### 1. Activate the virtual environment

From the repository root in PowerShell:

```powershell
. .\.venv\Scripts\Activate.ps1
```

If PowerShell blocks the script, allow scripts only for the current session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\.venv\Scripts\Activate.ps1
```

### 2. Install the local Python packages

```powershell
python -m pip install -r local/requirements.txt
```

The root `requirements.txt` is currently empty. Local packages are kept in `local/requirements.txt` because the first implementation target is the offline/local workflow.

### 3. Install and start Ollama

Install Ollama for Windows, then pull the two free models used by this project:

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Start the Ollama server in a separate PowerShell window:

```powershell
ollama serve
```

Check that the models are available:

```powershell
ollama list
```

## Ollama Configuration

`local/GenAI_ollama/src/ollama_config.py` is the shared configuration boundary. It reads these optional environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_CHAT_MODEL` | `llama3.2:3b` | Chat and generation model |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model for RAG |

Example PowerShell configuration:

```powershell
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_CHAT_MODEL = "llama3.2:3b"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
```

The helper exposes:

- `get_chat_model()`: creates a LangChain `ChatOllama` instance.
- `get_embeddings()`: creates a LangChain `OllamaEmbeddings` instance.
- `messages_to_text()`: converts LangChain message objects into readable text for logging or inspection.

Imports for the Ollama package are inside the factory functions. This keeps configuration importable even before the optional local packages are installed.

## Python Files

### `local/GenAI_ollama/src/01_langchain_local.py`

Purpose: demonstrate the smallest LangChain-to-Ollama path.

Code flow:

1. Import the shared `get_chat_model` factory.
2. `ask(question)` calls the model with `.invoke(question)`.
3. The returned message content is converted to a string.
4. When run directly, it asks Ollama to explain MLOps.

Run it:

```powershell
python "local/GenAI_ollama/src/01_langchain_local.py"
```

This is the best first smoke test because it verifies that Python, LangChain, Ollama, and the chat model are connected.

### `local/GenAI_ollama/src/02_rag_local.py`

Purpose: demonstrate local retrieval-augmented generation using FAISS.

Code flow:

1. Documents are represented as LangChain `Document` objects.
2. `RecursiveCharacterTextSplitter` divides larger documents into searchable chunks.
3. `OllamaEmbeddings` converts each chunk into a numeric vector.
4. FAISS stores the vectors in an in-memory index.
5. `similarity_search()` retrieves the three closest chunks for a question.
6. A prompt combines the retrieved context and question.
7. Ollama generates an answer constrained to that context.

Run it:

```powershell
python "local/GenAI_ollama/src/02_rag_local.py"
```

FAISS is a local vector search library, not a hosted database. The current implementation rebuilds the index on each run. A later improvement can persist it with `save_local()` and reload it with `load_local()`.

### `local/GenAI_ollama/src/03_langgraph_local.py`

Purpose: demonstrate a stateful LangGraph workflow.

Code flow:

1. `GraphState` defines the state fields: `question` and `answer`.
2. `generate_answer()` reads the question and calls Ollama.
3. `build_graph()` creates a `StateGraph`.
4. The graph starts at `generate_answer` and ends after the response is stored.
5. The compiled graph is invoked with an initial state.

Run it:

```powershell
python "local/GenAI_ollama/src/03_langgraph_local.py"
```

The graph is intentionally small. Later nodes can be added for retrieval, guardrail checks, tool calls, evaluation, retries, or human approval.

### `local/Predictive ML/src/02_drift_detection.py`

Purpose: detect distribution changes between a reference sample and a current sample.

Code flow:

1. Convert both inputs to floating-point NumPy arrays.
2. Create bins from reference-data quantiles.
3. Count values in each reference and current bin.
4. Convert counts to rates and clip zero rates to avoid logarithm errors.
5. Calculate the Population Stability Index, or PSI.
6. Classify the result as `stable`, `warning`, or `alert`.

The default interpretation is:

| PSI | Status |
| --- | --- |
| Less than `0.1` | `stable` |
| `0.1` to less than `0.25` | `warning` |
| `0.25` or greater | `alert` |

Run it:

```powershell
python "local/Predictive ML/src/02_drift_detection.py"
```

This is a baseline numeric drift check. Production monitoring should also consider missing values, categorical features, feature-specific thresholds, model quality, and alert delivery.

### `local/Predictive ML/src/01_model_training.py`

Purpose: provide a reproducible local training baseline.

Code flow:

1. Load the Iris dataset from scikit-learn.
2. Split features and labels into stratified training and test sets.
3. Standardize features with `StandardScaler`.
4. Train `LogisticRegression` inside a scikit-learn pipeline.
5. Measure test accuracy.
6. Save the fitted pipeline to `artifacts/iris_model.joblib` with joblib.

Run it:

```powershell
python "local/Predictive ML/src/01_model_training.py"
```

The saved artifact is a local example of the model package that a future SageMaker pipeline can create, register, evaluate, and deploy.

### `local/GenAI_ollama/src/04_api_server.py`

Purpose: expose the local chat model through an HTTP API.

Endpoints:

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/health` | Returns `{"status": "ok"}` without calling Ollama |
| `POST` | `/ask` | Validates a question and sends it to Ollama |

The request body for `/ask` is:

```json
{"question": "What is MLOps?"}
```

Start the API:

```powershell
uvicorn local.GenAI_ollama.src.04_api_server:app --host 127.0.0.1 --port 8000
```

Because Python module names cannot normally be imported with a leading numeric filename using standard dotted syntax, the most reliable option after changing into `local/GenAI/src` is:

```powershell
cd local/GenAI_ollama/src
uvicorn 04_api_server:app --host 127.0.0.1 --port 8000
```

Test the health endpoint from another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Test the chat endpoint:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ask -ContentType "application/json" -Body '{"question":"What is MLOps?"}'
```

If Ollama is unavailable, `/ask` returns HTTP `503` instead of exposing the underlying exception.

## Package Guide

All packages below are declared in `local/requirements.txt`. Version ranges provide compatible major-version boundaries while allowing normal patch and minor updates.

| Package | Why it is installed |
| --- | --- |
| `fastapi` | Defines the local HTTP API, request validation, response models, and endpoints. |
| `faiss-cpu` | Provides free, local vector similarity search for the RAG index. The CPU build does not require a GPU. |
| `joblib` | Serializes the trained scikit-learn pipeline to a local `.joblib` artifact. |
| `langchain-community` | Supplies community integrations, including the LangChain FAISS vector-store wrapper. |
| `langchain-ollama` | Connects LangChain to Ollama through `ChatOllama` and `OllamaEmbeddings`. |
| `langchain-text-splitters` | Splits source documents into chunks before embedding and retrieval. |
| `langgraph` | Builds and runs the stateful graph used by the orchestration example. |
| `numpy` | Provides arrays, quantiles, histograms, and numerical operations for drift detection. |
| `pandas` | Supports future tabular data loading and preprocessing workflows. It is declared now because the MLOps pipeline will use tabular data. |
| `scikit-learn` | Provides the example dataset, train/test split, preprocessing, classifier, pipeline, and accuracy metric. |
| `uvicorn[standard]` | Runs the FastAPI application as an ASGI server and includes standard server performance extras. |

### Important distinction: Python packages versus Ollama models

`pip install` installs Python libraries into `.venv`. Ollama models are separate files managed by the Ollama application:

```powershell
python -m pip install -r local/requirements.txt
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

The Python package `langchain-ollama` is only the connector. It does not include the Llama model or the embedding model.

## Folder and File Guide

### Root files

- `README.md`: project overview, setup, deployment notes, and roadmap.
- `requirements.txt`: reserved for shared or AWS-wide dependencies; currently empty.
- `.env.example`: reserved for documented environment variables; currently empty. Never commit actual credentials.
- `pytest.ini`: reserved for pytest configuration; currently empty.

### `local/`

- `local/GenAI_ollama/README.md`: local Ollama setup, model flow, Python file descriptions, testing commands, and troubleshooting.
- `local/requirements.txt`: dependencies for the Ollama, RAG, training, drift, and API examples.
- `local/GenAI_ollama/`: Ollama, LangChain, LangGraph, RAG, and API examples.
- `local/Predictive ML/`: drift detection and predictive model training examples.

### `tests/`

- `tests/test_api.py`: reserved for FastAPI endpoint tests.
- `tests/test_drift.py`: reserved for PSI and drift-status tests.
- `tests/test_preprocesssing.py`: reserved for preprocessing and model-training tests. The filename preserves the current repository spelling.

### `docker/`

- `docker/Dockerfile`: reserved for the application image definition.
- `docker/docker-compose.yml`: reserved for local application and service orchestration.

### `k8s/`

- `k8s/deployment.yaml`: reserved for Kubernetes deployment and service configuration.

### `terraform/`

- `terraform/mai.tf`: intended root Terraform configuration for providers and resources.
- `terraform/variable.tf`: intended Terraform input variables.
- `terraform/output.tf`: intended Terraform outputs.
- `terraform/modules/sagemaker/`: intended reusable SageMaker module; currently empty.
- `terraform/modules/vpc/`: intended reusable VPC module; currently empty.

## Recommended Implementation Order

1. Install local packages and verify the Ollama chat model with `GenAI_ollama/src/01_langchain_local.py`.
2. Verify `nomic-embed-text` and run the FAISS RAG example.
3. Expand the LangGraph workflow with retrieval and validation nodes.
4. Add unit tests for drift, training, API validation, and RAG helpers.
5. Add persistent FAISS indexes and configurable document loading.
6. Complete the Docker and Compose files for repeatable local serving.
7. Add AWS adapters for Bedrock, OpenSearch, and SageMaker behind configuration boundaries.
8. Complete Terraform modules and Kubernetes deployment after the application contract is stable.

## Troubleshooting

### `ollama` is not recognized

Install Ollama and restart PowerShell so the executable is available on `PATH`.

### `connection refused` at `localhost:11434`

Start Ollama with:

```powershell
ollama serve
```

### Model not found

Pull the required model again and confirm its exact name with `ollama list`:

```powershell
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### FAISS installation fails on Windows

FAISS availability depends on Python version and platform wheels. If the CPU wheel is unavailable for the active Python version, use a supported Python version in a fresh virtual environment or replace FAISS with another local vector store. Do not change the RAG interface until the storage decision is made.

### PowerShell says scripts are disabled

Use the temporary process-level policy documented above. It expires when the PowerShell window closes.
