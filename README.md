# PredML

PredML is a predictive machine-learning operations project for preparing data,
training and registering models, serving predictions, and monitoring model
behavior. It supports local development with Python and Docker and provides AWS
deployment infrastructure through SageMaker, S3, ECR, MLflow, Feature Store,
EventBridge, Terraform, and Jenkins.

## What this project does

The main PredML workflow is:

```text
Raw data
  -> preprocessing
  -> feature engineering and Feature Store
  -> model training
  -> model registration
  -> batch or real-time inference
  -> monitoring, forecasting, and rollback
```

The batch container uses the `STAGE` environment variable to run the required
pipeline stage:

- `01_preprocess`
- `02_feature_engineering`
- `03_feature_store`
- `04_train_model`
- `05_register_model`
- `06_batch_inference`
- `08_model_monitoring`
- `09_forecast`
- `10_rollback`

The real-time API is implemented separately in `src/07_realtime_inference.py`.

## Repository structure

```text
PredML/
|-- src/                         Python pipeline and inference code
|-- docker/                      Dockerfiles and container dependencies
|-- k8s/                         Kubernetes deployments and jobs
|-- AWS/                         AWS setup documentation and Terraform
|   `-- terraform/
|       |-- main.tf              Root Terraform module
|       |-- backend.tf            S3 remote-state configuration
|       |-- variables.tf         Terraform inputs
|       |-- outputs.tf            Terraform outputs
|       `-- modules/              Reusable AWS modules
|           |-- s3/
|           |-- ecr/
|           |-- iam/
|           |-- sagemaker/
|           `-- eventbridge/
|-- data/                        Local data files and generated datasets
|-- model/                       Local model artifacts
|-- predictions/                 Local prediction output
|-- monitoring/                  Local monitoring output
`-- mlruns/                      Local MLflow tracking data

cicd/
|-- Jenkinsfile-batch            Build/push batch image and trigger training
|-- Jenkinsfile-sagemaker-trigger
|                                 Wait for training promotion, then trigger inference
`-- Jenkinsfile.terraform        Validate, plan, apply, or destroy Terraform
```

## Prerequisites

- Python 3.11 or newer
- Docker, when running containers
- AWS CLI, when using AWS resources
- Terraform, when deploying infrastructure
- Jenkins, when using the CI/CD pipelines

AWS deployment requires permissions for the services used by the Terraform
modules. Configure AWS credentials through your local AWS profile or Jenkins
credentials; never store access keys in this repository.

## Local setup

Create a virtual environment from the repository root:

```powershell
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\.venv\Scripts\Activate.ps1
```

The execution-policy change applies only to the current PowerShell process.
It does not change the machine or user execution policy.

Install the project dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the local data-generation script from the `PredML` directory when needed:

```powershell
Set-Location .\PredML
python .\src\00_generate_raw_data.py
```

## Docker

Build the batch image from the repository root:

```powershell
docker build -t predml-batch:latest -f .\PredML\docker\batch.Dockerfile .\PredML
```

Run a training stage:

```powershell
docker run --rm `
  -e STAGE=04_train_model `
  predml-batch:latest
```

Build the real-time API image:

```powershell
docker build -t predml-api:latest -f .\PredML\docker\api.Dockerfile .\PredML
```

The Docker Compose configuration is available at
[`PredML/docker/docker-compose.yml`](./PredML/docker/docker-compose.yml).

## AWS infrastructure

The Terraform root module is
[`PredML/AWS/terraform`](./PredML/AWS/terraform). It provisions the supporting
PredML resources through reusable modules:

- S3 data and artifact bucket
- ECR repositories for batch and API images
- SageMaker and EventBridge IAM roles
- SageMaker MLflow tracking server
- SageMaker Feature Store feature group
- EventBridge schedules for batch inference and monitoring

Create local Terraform values without committing them:

```powershell
Set-Location .\PredML\AWS\terraform
Copy-Item .\terraform.tfvars.example .\terraform.tfvars
```

Review the values, then run:

```powershell
terraform init
terraform validate
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

The S3 state bucket configured in
[`backend.tf`](./PredML/AWS/terraform/backend.tf) must already exist before
normal `terraform init`. See [`PredML/AWS/Setup.txt`](./PredML/AWS/Setup.txt)
for the broader AWS setup and service workflow.

## CI/CD

[`cicd/Jenkinsfile-batch`](./cicd/Jenkinsfile-batch) runs on a weekly schedule
or a configured Git webhook. It:

1. Builds and pushes the `predml-batch` image when AWS batch sources change.
2. Builds and pushes the realtime API image to `predml-api` when the API sources
   change.
3. Pushes the immutable batch image tag for the separately managed
   [`cicd/Jenkinsfile-sagemaker-trigger`](./cicd/Jenkinsfile-sagemaker-trigger)
   job to validate and use.

[`cicd/Jenkinsfile-sagemaker-trigger`](./cicd/Jenkinsfile-sagemaker-trigger):

1. Verifies the training image tag exists in ECR.
2. Starts `PredML-Training-Pipeline` and waits for it to finish.
3. Requires a new `models/cost_forecaster/champion_promotion.json` marker,
   written by `05_register_model.py` only when the champion alias is promoted.
4. Starts the batch and realtime inference SageMaker pipelines in parallel.

On the first training run, no marker exists yet; the first registered model is
promoted to champion by design, and the newly created marker is accepted. On
later runs, the marker must change, so a challenger that does not beat the
current champion will not trigger inference.

Configure the trigger job as a separate Jenkins Pipeline job. Set its
`S3_BUCKET` and, when using an `S3_PREFIX`, `PROMOTION_MARKER_KEY` parameters
to match the AWS stage scripts. A rejected challenger therefore does not
trigger either inference pipeline.

The SageMaker pipeline definitions must pass the Terraform output
`mlflow_tracking_uri` to every AWS container as `MLFLOW_TRACKING_URI`. The AWS
stage code rejects a missing URI, so runs cannot silently use a local MLflow
store inside a container.

The Terraform Jenkins pipeline registers or updates four SageMaker pipelines
after a successful `apply`: training, batch inference, monitoring, and
rollback. Their definitions are generated by
[`PredML/AWS/pipelines/register_pipelines.py`](./PredML/AWS/pipelines/register_pipelines.py)
and use the Terraform-created SageMaker execution role, ECR batch image, S3
bucket, and MLflow tracking-server URI.

EventBridge schedules are currently disabled to avoid unattended SageMaker
executions and AWS costs. Inference is triggered by the champion-promotion
Jenkins job instead. Re-enable the EventBridge module in
[`PredML/AWS/terraform/main.tf`](./PredML/AWS/terraform/main.tf) when scheduled
execution is needed.

[`cicd/Jenkinsfile.terraform`](./cicd/Jenkinsfile.terraform) supports:

- Terraform validation and planning
- Manual approval before apply
- Manual approval before destroy
- S3 remote state initialization

Configure AWS credentials in Jenkins using credential IDs rather than putting
keys in a Jenkinsfile.

The reusable Jenkins agent image and WSL Docker socket setup are documented in
[`cicd/README.md`](./cicd/README.md).

## Kubernetes

Kubernetes manifests for batch jobs, scheduled monitoring, MLflow, and related
services are under [`PredML/k8s`](./PredML/k8s). Review the manifests and
namespace configuration before applying them to a cluster.

## Security and generated files

Do not commit:

- `.venv` or any other Python virtual-environment directory
- `.env` files, AWS credentials, Terraform variable files, or state files
- private keys, certificates, local model files, datasets, or MLflow runs
- generated caches, predictions, and monitoring artifacts

The root [`.gitignore`](./.gitignore) excludes these files. Before pushing,
check the staged file list:

```powershell
git status --short
git diff --cached --name-only
```

If a secret was committed previously, remove it from the repository history
and rotate the credential; adding it to `.gitignore` does not remove it from
Git history.
