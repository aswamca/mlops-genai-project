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

- Python 3.12 recommended for the local environment
- Docker, when running containers
- AWS CLI, when using AWS resources
- Terraform, when deploying infrastructure
- Jenkins, when using the CI/CD pipelines

AWS deployment requires permissions for the services used by the Terraform
modules. Configure AWS credentials through your local AWS profile or Jenkins
credentials; never store access keys in this repository.

## Local setup - run in order

Use the existing Python 3.12 environment because it is compatible with the pinned MLflow and data-science packages.

### 1. Activate the existing `.venvpython312` environment

From the repository root:

```powershell
cd E:\Projects\mlops-genai-project
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
. .\.venvpython312\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -c "import sys, mlflow; print(sys.version); print('MLflow', mlflow.__version__)"
```

The expected Python version is `3.12.x` and the expected MLflow version is `3.18.0`. Do not create or use `.venv` for this run unless you also install Python 3.12 dependencies there.

### 2. Start MLflow

Open one terminal, activate the environment, and keep this terminal running:

```powershell
cd E:\Projects\mlops-genai-project
. .\.venvpython312\Scripts\Activate.ps1
python -m mlflow server `
  --backend-store-uri "sqlite:///E:/Projects/mlops-genai-project/PredML/mlruns/mlruns.db" `
  --default-artifact-root "mlflow-artifacts:/" `
  --artifacts-destination "file:///E:/Projects/mlops-genai-project/PredML/mlruns/artifacts" `
  --serve-artifacts `
  --host 127.0.0.1 `
  --port 5000
```

Do not use `mlflow.exe` if Windows Application Control blocks the launcher. Use `python -m mlflow` instead.

Open the MLflow UI:

```text
http://127.0.0.1:5000
```

### 3. Run the complete training pipeline

Open a second terminal:

```powershell
cd E:\Projects\mlops-genai-project
. .\.venvpython312\Scripts\Activate.ps1
$env:MLFLOW_TRACKING_URI = "http://127.0.0.1:5000"
cd .\PredML\src

python 00_generate_raw_data.py
python 01_preprocess.py
python 02_feature_engineering.py
python 03_feature_store.py
python 04_train_model.py
python 05_register_model.py
```

Stage explanations:

1. `00_generate_raw_data.py` creates the demo source data and intentionally injects missing values for testing.
2. `01_preprocess.py` cleans missing and outlier values.
3. `02_feature_engineering.py` creates sales, cost, time and lag features.
4. `03_feature_store.py` writes offline and online feature files.
5. `04_train_model.py` trains and registers an XGBoost challenger.
6. `05_register_model.py` compares test MAPE and promotes or rejects the challenger.

Lower test MAPE is better. A challenger is promoted only when it is lower than the current champion. A missing champion makes the first registered model the champion.

### 4. Run batch inference

From the same pipeline terminal:

```powershell
python 06_batch_inference.py
```

Check the generated CSV under:

```text
PredML/predictions/batch/
```

### 5. Start the realtime API

Keep MLflow running, open a third terminal, and run:

```powershell
cd E:\Projects\mlops-genai-project
. .\.venvpython312\Scripts\Activate.ps1
$env:MLFLOW_TRACKING_URI = "http://127.0.0.1:5000"
cd .\PredML
python .\src\07_realtime_inference.py
```

Open Swagger UI:

```text
http://localhost:8000/docs
```

Use `GET /health` and `POST /predict` for a basic UI test:

```json
{
  "product_id": "PRD001",
  "region": "NA",
  "sales": 190000
}
```

Other useful URLs:

```text
http://localhost:8000/
http://localhost:8000/health
http://localhost:8000/redoc
http://localhost:8000/openapi.json
```

### 6. Optional monitoring and rollback

```powershell
python 08_model_monitoring.py baseline
python 08_model_monitoring.py monitor
python 10_rollback.py --list
python 10_rollback.py --to-version 4
```

Replace `4` with an existing registered MLflow version for rollback testing.

## Docker setup - run in order

The Docker Compose configuration is at [`PredML/docker/docker-compose.yml`](./PredML/docker/docker-compose.yml). Docker provides an isolated local MLflow server, API container and batch-job container.

Run all commands from the `PredML` directory.

### 1. Generate raw data locally

Docker intentionally does not generate the raw CSV. Create it with the Python environment:

```powershell
cd E:\Projects\mlops-genai-project
. .\.venvpython312\Scripts\Activate.ps1
cd .\PredML
python .\src\00_generate_raw_data.py
```

Confirm the source file exists:

```text
PredML/data/01_raw/raw_data_pharma_transactions.csv
```

### 2. Build and start MLflow and the API

```powershell
cd E:\Projects\mlops-genai-project\PredML
docker compose -f .\docker\docker-compose.yml build
docker compose -f .\docker\docker-compose.yml up -d mlflow api
docker compose -f .\docker\docker-compose.yml ps
```

Open:

```text
MLflow: http://localhost:5000
API: http://localhost:8000
Swagger: http://localhost:8000/docs
```

### 3. Run training stages in sequence

Run each stage with the `STAGE` environment variable:

```powershell
docker compose -f .\docker\docker-compose.yml run --rm -e STAGE=01_preprocess batch
docker compose -f .\docker\docker-compose.yml run --rm -e STAGE=02_feature_engineering batch
docker compose -f .\docker\docker-compose.yml run --rm -e STAGE=03_feature_store batch
docker compose -f .\docker\docker-compose.yml run --rm -e STAGE=04_train_model batch
docker compose -f .\docker\docker-compose.yml run --rm -e STAGE=05_register_model batch
```

Do not skip preprocessing or feature-store stages. Training reads the offline feature parquet created by stage 3.

### 4. Run batch inference

```powershell
docker compose -f .\docker\docker-compose.yml run --rm -e STAGE=06_batch_inference batch
```

Results are written to:

```text
PredML/predictions/batch/
```

### 5. Test the Docker API

Open Swagger:

```text
http://localhost:8000/docs
```

Then test:

- `GET /health`
- `POST /predict` with `PRD001`, `NA`, and sales `190000`
- `POST /forecast` using valid start/end dates

PowerShell health check:

```powershell
Invoke-RestMethod -Method Get -Uri http://localhost:8000/health
```

PowerShell prediction check:

```powershell
$body = @{ product_id='PRD001'; region='NA'; sales=190000 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/predict -ContentType 'application/json' -Body $body
```

### 6. Stop Docker

Stop the API and MLflow containers:

```powershell
docker compose -f .\docker\docker-compose.yml stop api mlflow
```

Remove containers and the Compose network:

```powershell
docker compose -f .\docker\docker-compose.yml down
```

Data, MLflow metadata and predictions remain on the host because the Compose file mounts `data`, `mlruns`, `model`, `predictions` and `monitoring`.

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

## Jenkins, SageMaker and AWS deployment - run in order

This section starts after AWS infrastructure has been created by Terraform.

### 1. Open Jenkins and complete the initial login

Jenkins is installed locally as a Windows service. Open it in a browser:

```text
http://localhost:8081
```

If Jenkins is using a different port, open the Jenkins Windows service configuration or check the Jenkins URL shown in the setup wizard. This project’s confirmed local listener is port `8081`, not the default `8080`.

When Jenkins opens the setup wizard, read the initial administrator password:

```powershell
Get-Content "C:\ProgramData\Jenkins\.jenkins\secrets\initialAdminPassword"
```

Then:

1. Enter the initial administrator password.
2. Select **Install suggested plugins**.
3. Create a Jenkins administrator username and password.
4. Confirm the Jenkins URL as:

```text
http://localhost:8081/
```

A normal Jenkins user login is then:

```text
http://localhost:8081/login
```

### 2. Configure Jenkins credentials

Create these Jenkins credentials:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_ACCOUNT_ID`

Use IAM roles or Jenkins credentials rather than committing AWS keys to Git.

### 3. Create Jenkins jobs

Create three Pipeline jobs:

1. `PredML-Terraform` using [`cicd/Jenkinsfile.terraform`](./cicd/Jenkinsfile.terraform).
2. `PredML-Images` using [`cicd/Jenkinsfile-batch`](./cicd/Jenkinsfile-batch).
3. `PredML-SageMaker-Trigger` using [`cicd/Jenkinsfile-sagemaker-trigger`](./cicd/Jenkinsfile-sagemaker-trigger).

### 4. Create AWS infrastructure

Run `PredML-Terraform` with `TF_ACTION=plan`, review the plan, then run it with `TF_ACTION=apply`.

Confirm that Terraform created:

- S3 bucket
- SageMaker MLflow server
- SageMaker Feature Store resources
- ECR batch and API repositories
- Required IAM roles

### 5. Register SageMaker pipelines

From the repository root:

```powershell
python .\cicd\register_sagemaker_pipelines.py
```

The pipeline registration script creates the training and inference pipelines used by Jenkins.
Each execution-graph step has a description of its specific work instead of a
generic “Process data” label.

### 6. Build and push images

Run `PredML-Images` in Jenkins. It builds and pushes:

- `predml-batch:<build-number>`
- `predml-batch:latest`
- `predml-api:<build-number>`
- `predml-api:latest`

Use **Build with Parameters** and select `BUILD_TARGET`:

- `auto` builds the image(s) affected by changed files (the default for push triggers).
- `batch` builds only the batch image.
- `api` builds only the realtime API image.
- `both` builds both images.

After a successful push, Jenkins removes those local Docker tags and keeps
the three newest numeric build images in each ECR repository. The mutable
`latest` tag remains on the current image.

When running the SageMaker trigger manually, enter only the immutable batch image tag, such as `16`, in `ECR_IMAGE_TAG`. Do not enter a full image URI or `ECR_IMAGE_TAG=16`.

### 7. Run SageMaker training and promotion gate

Run `PredML-SageMaker-Trigger` with:

```text
S3_BUCKET=<terraform bucket>
PROMOTION_MARKER_KEY=models/cost_forecaster/champion_promotion.json
ECR_IMAGE_TAG=<immutable build number>
TRAINING_PIPELINE=PredML-Training-Pipeline
BATCH_PIPELINE=PredML-Batch-Inference-Pipeline
REALTIME_PIPELINE=PredML-Realtime-Inference-Pipeline
```

The Jenkins job:

1. Verifies the batch image in ECR.
2. Records the previous promotion marker.
3. Starts the SageMaker training pipeline.
4. Waits for success or reports SageMaker step failures.
5. Checks whether the promotion marker changed.
6. Starts batch and realtime inference only after a champion promotion.

The first registered model is promoted automatically. Later challengers are promoted only when their test MAPE is lower than the current champion.

### 8. Verify SageMaker results

Check in AWS:

- SageMaker > Pipelines for training and inference execution status
- MLflow for registered versions and `champion`/`previous` aliases
- S3 `processed/`, `features/`, `output/predictions/batch/` and `models/cost_forecaster/` prefixes
- CloudWatch logs for pipeline and container failures

### 9. UI and API testing

After the realtime inference pipeline is deployed or the EKS API is restarted:

```text
https://<your-route53-name>/health
https://<your-route53-name>/docs
```

Use `POST /predict` with:

```json
{
  "product_id": "PRD001",
  "region": "NA",
  "sales": 190000
}
```

Confirm the response includes:

- `predicted_cost`
- `model_version`
- `confidence`
- `feature_as_of`
- `feature_source`

A rejected challenger does not change the champion marker and does not start batch or realtime inference.

### End-to-end execution flow

The complete flow after a training run is:

```text
Jenkins image validation
        |
        v
SageMaker training pipeline
  01_preprocess
        |
  02_feature_engineering
        |
  03_feature_store
        |
  04_train_model
        |
  05_register_model
        |
        v
MLflow champion/challenger decision
        |
        +-- challenger rejected --> retain current champion
        |                           SageMaker step mirrors it only if missing
        |
        +-- champion promoted
                v
  11_register_sagemaker_model
        |
        +--> SageMaker Model Registry
             PendingManualApproval
             (no endpoint created yet)
```

The stages in the training pipeline run sequentially. `01_preprocess` reads
the raw input from the S3 `input/` prefix, `02_feature_engineering` creates
the model features, and `03_feature_store` writes the offline and online
features. `04_train_model` trains a challenger and logs its model, metrics,
and metadata to the SageMaker MLflow Tracking Server.

Preprocessing treats `actual_cost` as a required training label. Rows where
`actual_cost` is missing are excluded from the training dataset and written to
`processed/ops_data_quality_review.csv` (or `data/02_processed/` locally) for
the Ops team to verify and backfill. The pipeline never imputes a missing
actual cost, because doing so would create a fabricated target. Missing
`sales` is median-imputed within `product_id` and `region`; if no such median
exists, that row is also sent to the Ops review file.

`05_register_model` compares the challenger `test_mape` with the current
champion. The first registered model is promoted automatically. On later
runs, the challenger is promoted only when it improves the champion. A
successful promotion assigns the MLflow `champion` alias and writes
`models/cost_forecaster/champion_promotion.json` to S3.

After stage 5, AWS-only stage `11_register_sagemaker_model` mirrors the
current MLflow champion into the SageMaker Model Registry. It creates a model
package group named `predml-cost-forecaster` if needed and marks each new
package `PendingManualApproval`. It does not change MLflow registration,
approve the SageMaker package, or create/update an endpoint. Re-running the
stage for the same MLflow version detects the existing package and skips it.
If a challenger is rejected, the SageMaker step sees the unchanged current
champion; it registers that champion only if it has not yet been mirrored.

The future deployment extension should start only after an authorized person
changes the SageMaker package status to `Approved`. A separate deployment
pipeline, triggered by a SageMaker Model Package State Change event, can then
create a SageMaker Model, endpoint configuration and endpoint. Endpoint
creation, update, traffic shifting and rollback are intentionally not part of
the current stage.

The trigger Jenkins job records the promotion marker before starting
training, waits for the SageMaker execution to finish, and compares the
marker again afterward. This prevents a rejected challenger from triggering
inference. If training fails, stops, or times out, the job stops before
inference. If a new champion was promoted, batch and realtime inference are
started in parallel.

Promoting a model directly in the MLflow UI does not automatically start the
batch inference pipeline. The current trigger is Jenkins, not an MLflow
webhook. The trigger job must be run after the promotion, and the promotion
marker at `models/cost_forecaster/champion_promotion.json` must change. The
marker is written by `05_register_model.py` during the normal training flow;
an alias change made manually in the MLflow UI does not write this marker.
The current trigger job is a training-and-gate job, not a post-promotion
listener; starting it will start another training execution. Therefore, for a
manually promoted model, start the batch inference SageMaker pipeline
manually from the AWS Console. If the EKS API loads the champion only during
startup, perform a rolling restart after the promotion so realtime pods load
the new model version.

### Why MLflow is required for batch inference

Batch inference does not load an arbitrary model file from a fixed S3 path.
`06_batch_inference` first resolves the model version assigned to the MLflow
`cost-forecaster@champion` alias, reads its feature contract and metadata, and
loads the registered model using an MLflow `models:/` URI. It then reads the
offline feature data from S3, scores the configured inference window, and
writes timestamped prediction files below
`output/predictions/batch/`.

S3 stores the datasets, feature files, model artifacts, and prediction
outputs. MLflow stores the registry state that identifies which model version
is the current champion. Therefore the SageMaker MLflow Tracking Server must
be running and reachable for both training/registration and batch inference.
The inference container receives the same `MLFLOW_TRACKING_URI` as the
training container. Use the Terraform-created tracking-server ARN; do not
replace it with a local MLflow URL.

The realtime API uses the same champion alias. At startup it resolves and
loads the champion model, validates its feature contract, loads the online
features from S3, and then serves prediction and forecast requests. This
keeps batch and realtime inference aligned to the same promoted model version.

### Manual realtime inference deployment with a GUI on EKS

The realtime API exposes these endpoints:

```text
GET  /health
POST /predict
POST /forecast
```

The API listens on port `8000`. The GUI can call the API through the ALB
hostname or through a Route 53 name. Deploy the GUI as a separate frontend
service in the same EKS cluster, or host it separately and allow its origin in
the API's CORS configuration before exposing it publicly.

The following is the recommended manual AWS Console order after a champion
model has been promoted.

#### 1. Build and push the realtime API image

Run the batch Jenkins job, or build the API image locally from the repository
root and push it to the `predml-api` ECR repository:

```powershell
docker build -t predml-api:<tag> -f .\PredML\docker\api.Dockerfile .\PredML
docker tag predml-api:<tag> <account-id>.dkr.ecr.<region>.amazonaws.com/predml-api:<tag>
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/predml-api:<tag>
```

Use an immutable tag rather than `latest` for the EKS deployment. The
`predml-api` repository is created by Terraform. Confirm that the EKS worker
node role or pod identity can pull from this ECR repository.

#### 2. Prepare the EKS cluster

In the AWS Console:

1. Open **EKS** and select the target cluster.
2. Confirm that the cluster has healthy managed nodes or Fargate capacity.
3. Confirm that the cluster is in the same VPC as the ALB subnets.
4. Confirm that the cluster IAM and networking configuration allows:
   - ECR image pulls.
   - S3 access to the project bucket.
   - Access to the SageMaker MLflow Tracking Server.
5. Install or verify the AWS Load Balancer Controller. It is required for
   the Kubernetes `Ingress` resource to create an AWS Application Load
   Balancer.

Create a namespace such as `predml` and deploy the API into it. The existing
files under [`PredML/k8s`](./PredML/k8s) are useful starting points, but the
API deployment must be adapted before use in EKS:

- Replace `predml-local/api:latest` with the immutable ECR image URI.
- Replace local-development PVCs with S3-backed application behavior or
  production storage appropriate for the deployment.
- Do not use the local `http://mlflow:5000` configuration. Supply the
  SageMaker MLflow Tracking Server ARN through `MLFLOW_TRACKING_URI`.
- Store credentials and sensitive configuration in Kubernetes Secrets or an
  AWS Secrets Manager integration, not in a committed ConfigMap.

#### 3. Configure API runtime settings

Configure the API Deployment with at least:

```text
AWS_REGION=<region>
S3_BUCKET=<terraform-created-bucket>
S3_PREFIX=<optional-prefix>
MLFLOW_TRACKING_URI=<terraform-output-mlflow_tracking_server_arn>
```

The EKS pod role must be allowed to read the champion model metadata from
MLflow, read the online feature and product data from S3, and write any
runtime outputs required by the API. The pod should not use long-lived AWS
access keys.

The API readiness and liveness probes should call:

```text
GET /health
```

Only route traffic to pods that return HTTP 200 from this endpoint. The
response includes the loaded model version, which is useful for confirming
that the pod started with the expected champion.

#### 4. Deploy the API Service

Create a Kubernetes `Service` that selects the API pods and exposes port
`8000` internally:

```text
Service port: 8000
Target port: 8000
Protocol: TCP
Type: ClusterIP
```

Keep the Service as `ClusterIP`; the public endpoint should be provided by
the ALB Ingress rather than by exposing every pod directly.

#### 5. Deploy the GUI application

Build the GUI application and push its image to a separate ECR repository,
for example `predml-ui`. Configure the GUI at build time or runtime with the
internal API URL, such as:

```text
http://predml-api.predml.svc.cluster.local:8000
```

For a browser-based GUI, prefer exposing the API through the same ALB
hostname, using a path such as `/api`, or through a separate API hostname.
This avoids browser CORS problems and keeps the API private behind the ALB.

Deploy the GUI with its own Kubernetes Deployment and ClusterIP Service.
The GUI container should listen on the port configured by its image, commonly
`80` or `8080`. Confirm that the GUI sends:

- `POST /predict` with `product_id`, `region`, and `sales`.
- `POST /forecast` with the required forecast request fields.
- `GET /health` for its own readiness check, if supported.

#### 6. Create the ALB Ingress

Create an `Ingress` using the AWS Load Balancer Controller with:

- Internet-facing scheme if the GUI is public.
- HTTPS listener on port `443`.
- ACM certificate for the intended DNS name.
- Target type `ip` for pod targets.
- A health check path of `/health`.
- A rule routing `/api` to `predml-api` and `/` to the GUI Service. If the
  `/api` prefix is used, configure an ALB path rewrite (or configure the
  frontend to call a dedicated API hostname), because the application routes
  are `/health`, `/predict`, and `/forecast`, without an `/api` prefix.

The exact Ingress annotations depend on the installed AWS Load Balancer
Controller version. Verify that the ALB target group reports the API and GUI
targets as **healthy** before testing from a browser. Restrict the ALB
security group to the required inbound ports and allow the worker/pod
security groups to receive traffic from the ALB security group.

#### 7. Configure Route 53

After the Ingress creates the ALB:

1. Copy the ALB DNS name from the Ingress status or the EC2 **Load
   Balancers** page.
2. Open **Route 53** and select the hosted zone for the application domain.
3. Create an **A** record with **Alias** enabled.
4. Select the Application Load Balancer as the alias target.
5. Point the application name, for example `forecast.example.com`, to the
   ALB.
6. Wait for DNS propagation and open the HTTPS URL.

The ACM certificate must cover the exact Route 53 name. If the GUI and API
use separate hostnames, create an ALB host rule for each name and configure
the GUI's API base URL accordingly.

#### 8. Validate realtime inference from the GUI

Validate in this order:

1. Open `https://<route53-name>/health` or the API health path routed by the
   ALB.
2. Confirm that the response reports the expected champion model version.
3. Open the GUI and submit a prediction request.
4. Confirm that the GUI receives the `predicted_cost`, `model_version`, and
   feature metadata from `/predict`.
5. Test a forecast request through `/forecast`.
6. Check EKS pod logs, ALB target health, and CloudWatch logs if a request
   fails.

When a new model is promoted, restart or roll out the API Deployment if the
application only loads the champion during startup. Then repeat the health
check and confirm that all ready pods report the new model version. Keep the
old image tag available for a quick Deployment rollback.

### FastAPI versus a SageMaker real-time endpoint

Enterprise systems commonly use FastAPI and SageMaker together, but they
serve different purposes. SageMaker is typically used for training,
processing, model registration, and optionally managed model hosting.
FastAPI is typically used for the application API, request validation,
authentication, business logic, and orchestration of several backend
services.

This project currently uses the following architecture:

```text
SageMaker Pipelines
  └── training and batch processing

SageMaker MLflow Tracking Server
  └── model registry and champion alias

FastAPI on EKS
  └── realtime prediction and forecasting API

ALB + Route 53
  └── external access for the GUI and API
```

There is no SageMaker real-time inference endpoint in this design. The
FastAPI application loads the model assigned to the MLflow `champion` alias
and performs inference inside the EKS pod. The GUI calls the FastAPI
endpoints through the ALB.

A SageMaker real-time endpoint is an alternative, not a requirement. A
different enterprise architecture could use FastAPI as an application layer
and SageMaker as the managed model-serving layer:

```text
GUI
  |
  v
ALB / API layer
  |
  v
FastAPI on EKS
  |
  v
SageMaker real-time endpoint
  |
  v
Model
```

That alternative is useful when model hosting, model autoscaling, canary
deployments, shadow testing, or independent scaling need to be managed by
SageMaker. It also separates application/API scaling from model-serving
scaling. The current EKS design is suitable when the API contains substantial
business logic, multiple endpoints, custom validation, or other integrations,
and the team wants Kubernetes to manage the complete inference service.

For this project, keep SageMaker Pipelines for training and batch processing,
MLflow for model registration and champion promotion, and FastAPI on EKS for
the GUI-facing realtime API. Introduce a SageMaker real-time endpoint later
only if managed model hosting or independent model-serving scale becomes a
specific requirement. The Jenkins parameter named
`PredML-Realtime-Inference-Pipeline` should not be interpreted as a
SageMaker hosted endpoint; the current realtime serving target is the FastAPI
application deployed on EKS.

The monitoring and rollback pipelines are separate from this promotion flow.
Monitoring can be run against the generated data and rollback is an explicit
operation; neither is automatically started by the trigger job.

The SageMaker pipeline definitions must pass the Terraform output
`mlflow_tracking_server_arn` to every AWS container as `MLFLOW_TRACKING_URI`.
The AWS `sagemaker-mlflow` plugin uses the tracking-server ARN for SigV4
authentication; the HTTPS tracking URL alone is not sufficient. The AWS stage
code rejects a missing URI, so runs cannot silently use a local MLflow store
inside a container.

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
