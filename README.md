mlops-genai-project
A comprehensive MLOps and Generative AI implementation project. The project brings together LLM orchestration, retrieval-augmented generation, model lifecycle automation, monitoring, and cloud infrastructure into one practical reference implementation.
MLOps GenAI Project
A comprehensive MLOps and Generative AI implementation project. The project brings together LLM orchestration, retrieval-augmented generation, model lifecycle automation, monitoring, and cloud infrastructure into one practical reference implementation.

The planned implementation covers:

LangChain and LangGraph for LLM orchestration and workflow control
RAG using FAISS for local development and OpenSearch for a managed search backend
AWS Bedrock integration, including model access and guardrails
SageMaker MLOps pipelines for training, evaluation, and deployment
Data drift detection and model monitoring
Terraform infrastructure as code for AWS resources
Docker and Kubernetes deployment workflows
Project status: The local Ollama examples are implemented. Tests, container manifests, Kubernetes configuration, and Terraform infrastructure remain planned scaffold work.

Table of Contents
Project Overview
Quick Start
Project Structure
File Descriptions
AWS vs Local
Prerequisites
Running Each Script
Infrastructure Deployment
Testing
Development Roadmap
Implementation Guide
How the Local Project Flow Works
In simple terms, Ollama is the local server that runs the downloaded AI model. Our Python code does not run the model directly. It sends a request to Ollama, and Ollama passes that request to the selected model, such as llama3.2:1b.

You ask a question
	|
	v
Python application
	|
	v
LangChain or LangGraph
	|
	v
Ollama server at http://localhost:11434
	|
	v
llama3.2:1b generates the answer
	|
	v
Answer returns to the Python application
The roles are:

Python application: Contains our project logic and sends questions.
LangChain/LangGraph: Connects the Python code to the model and manages the workflow.
Ollama server: Runs locally and receives model requests.
llama3.2:1b: The lightweight chat model that generates answers.
nomic-embed-text: Converts documents and questions into vectors for RAG search.
FAISS: Searches those vectors locally to find relevant document content before the chat model answers.
For a normal chat request:

Python -> LangChain -> Ollama server -> llama3.2:1b -> response
For a RAG request:

Documents -> nomic-embed-text -> FAISS
Question -> nomic-embed-text -> FAISS finds relevant documents
Question plus relevant documents -> Ollama -> llama3.2:1b -> response
Ollama, the chat model, and the embedding model run locally. The application only needs the Ollama server available at http://localhost:11434.

Project Overview
The project is organized around two complementary paths:

Local experimentation: Run orchestration, RAG, drift detection, model training, and API examples locally while developing and testing.
AWS deployment: Move production-oriented workloads to Bedrock, OpenSearch, SageMaker, and infrastructure provisioned with Terraform.
The expected end-to-end flow is:

Data -> preprocessing and training -> evaluation -> model/API deployment
										 |
										 v
							  monitoring and drift detection

User question -> LangChain/LangGraph workflow -> FAISS or OpenSearch retrieval
										 |
										 v
							  Bedrock model and guardrails
Quick Start
Create and activate a virtual environment from the repository root:

python -m venv .venv
Windows PowerShell:

.\.venv\Scripts\Activate.ps1
If PowerShell reports that running scripts is disabled, allow scripts only for the current PowerShell session and activate the environment again:

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\.venv\Scripts\Activate.ps1
The Process scope is temporary and does not change the machine or user execution policy.

macOS/Linux:

source .venv/bin/activate
Install dependencies after they are added to the relevant requirements file:

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r local/requirements.txt
Install the lightweight local Ollama chat model and the embedding model used for RAG:

ollama pull llama3.2:1b
ollama pull nomic-embed-text
ollama list
Start Ollama in a separate PowerShell window if it is not already running:

ollama serve
Use the lightweight chat model for this project:

$env:OLLAMA_CHAT_MODEL = "llama3.2:1b"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"
Then run the local examples from the repository root as described in Running Each Script.

Project Structure
.
|-- local/
|   |-- README.md
|   |-- requirements.txt
|   |-- Predictive ML/
|   |   `-- src/
|   |       |-- 01_model_training.py
|   |       `-- 02_drift_detection.py
|   `-- GenAI/
|       `-- src/
|           |-- 01_langchain_local.py
|           |-- 02_rag_local.py
|           |-- 03_langgraph_local.py
|           |-- 04_api_server.py
|           `-- ollama_config.py
|-- tests/
|   |-- test_api.py
|   |-- test_drift.py
|   `-- test_preprocesssing.py
|-- docker/
|   |-- Dockerfile
|   `-- docker-compose.yml
|-- k8s/
|   `-- deployment.yaml
|-- terraform/
|   |-- mai.tf
|   |-- output.tf
|   |-- variable.tf
|   `-- modules/
|       |-- sagemaker/
|       `-- vpc/
|-- requirements.txt
|-- pytest.ini
`-- README.md
File Descriptions
Local source
local/README.md: Local Ollama setup, model flow, Python files, and testing commands.
local/GenAI/src/01_langchain_local.py: Local LangChain orchestration example.
local/GenAI/src/02_rag_local.py: Local RAG workflow using a vector index such as FAISS.
local/GenAI/src/03_langgraph_local.py: LangGraph workflow demonstrating stateful or multi-step agent orchestration.
local/Predictive ML/src/02_drift_detection.py: Data or feature drift detection and monitoring example.
local/Predictive ML/src/01_model_training.py: Model preprocessing, training, and evaluation workflow.
local/GenAI/src/04_api_server.py: API entry point for serving the project functionality.
Tests and dependencies
tests/: Automated tests for the API, drift detection, and preprocessing/training behavior.
requirements.txt: Shared project dependencies.
local/requirements.txt: Dependencies specific to local experiments.
pytest.ini: Pytest configuration.
Deployment and infrastructure
docker/Dockerfile: Image definition for packaging the application.
docker/docker-compose.yml: Local multi-container orchestration.
k8s/deployment.yaml: Kubernetes deployment configuration.
terraform/mai.tf: Root Terraform resources and providers.
terraform/variable.tf: Configurable Terraform inputs.
terraform/output.tf: Values exposed after deployment.
terraform/modules/sagemaker/: Reusable SageMaker infrastructure module.
terraform/modules/vpc/: Reusable VPC/network infrastructure module.
AWS vs Local
Capability	Local development	AWS-oriented deployment
LLM provider	Local or mock model, depending on implementation	Amazon Bedrock
Safety controls	Application-level validation and test doubles	Bedrock Guardrails
Vector search	FAISS	Amazon OpenSearch
Model training	Local Python workflow	SageMaker processing/training pipelines
Monitoring	Local drift checks and logs	SageMaker Model Monitor and cloud observability
Infrastructure	Local Python, Docker, or Compose	Terraform-managed AWS resources
Serving	Local API server	Docker/Kubernetes or AWS service deployment
Use the local path for fast iteration and low-cost testing. Use the AWS path when validating managed services, production-like permissions, scalability, and deployment automation.

Prerequisites
Local
Python 3.10 or newer
pip and venv
Git
Docker Desktop, if using the container workflow
A Kubernetes cluster and kubectl, if using the Kubernetes workflow
AWS
An AWS account with the required service quotas and Bedrock model access enabled
AWS CLI configured with credentials for the target account
Terraform installed
IAM permissions for Bedrock, OpenSearch, SageMaker, networking, and supporting resources
An AWS region selected for all services
Keep credentials out of source control. Store configuration in environment variables, AWS profiles, or a secrets manager. Populate .env.example when the project configuration is implemented, but do not commit real secrets.

Running Each Script
Run commands from the repository root:

python "local/GenAI/src/01_langchain_local.py"
python "local/GenAI/src/02_rag_local.py"
python "local/GenAI/src/03_langgraph_local.py"
python "local/Predictive ML/src/02_drift_detection.py"
python "local/Predictive ML/src/01_model_training.py"
python "local/GenAI/src/04_api_server.py"
The scripts are currently placeholders, so these commands will not provide useful output until their implementations and dependencies are added. The intended execution order for a completed local workflow is:

Run the LangChain and LangGraph examples.
Build and query the local RAG index.
Train or load a model with the training script.
Run drift detection against reference and current datasets.
Start the API server and exercise it with the API tests.
Infrastructure Deployment
Review and customize Terraform variables before provisioning anything:

cd terraform
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
After deployment, inspect exported values with:

terraform output
Destroy resources only when they are no longer needed:

terraform destroy
For a local container workflow, once docker/Dockerfile and Compose configuration are implemented:

docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up
For Kubernetes, configure the target context and apply the manifest after the image has been built and made available to the cluster:

kubectl config current-context
kubectl apply -f k8s/deployment.yaml
kubectl get deployments,pods,services
Testing
Run the test suite from the repository root:

python -m pytest
As each component is implemented, add focused unit tests and integration tests for API behavior, preprocessing, drift calculations, retrieval quality, and deployment configuration.

Development Roadmap
Add shared and local Python dependencies plus environment configuration.
Implement the LangChain, LangGraph, and RAG examples with mock-friendly local tests.
Implement preprocessing, model training, drift detection, and API serving.
Add Bedrock and guardrail adapters behind clear configuration boundaries.
Build SageMaker pipeline and monitoring integrations.
Complete Terraform modules and validate infrastructure with terraform plan.
Package the API with Docker and deploy it to Kubernetes.
Expand CI checks for tests, linting, security scanning, and infrastructure validation.