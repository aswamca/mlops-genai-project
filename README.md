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
        +-- challenger rejected --> stop; no inference is started
        |
        +-- champion promoted
                |
                +--> batch inference pipeline
                |      06_batch_inference
                |      predictions written to S3
                |
                +--> realtime inference pipeline
                       API loads the champion model
```

The stages in the training pipeline run sequentially. `01_preprocess` reads
the raw input from the S3 `input/` prefix, `02_feature_engineering` creates
the model features, and `03_feature_store` writes the offline and online
features. `04_train_model` trains a challenger and logs its model, metrics,
and metadata to the SageMaker MLflow Tracking Server.

`05_register_model` compares the challenger `test_mape` with the current
champion. The first registered model is promoted automatically. On later
runs, the challenger is promoted only when it improves the champion. A
successful promotion assigns the MLflow `champion` alias and writes
`models/cost_forecaster/champion_promotion.json` to S3.

The trigger Jenkins job records the promotion marker before starting
training, waits for the SageMaker execution to finish, and compares the
marker again afterward. This prevents a rejected challenger from triggering
inference. If training fails, stops, or times out, the job stops before
inference. If a new champion was promoted, batch and realtime inference are
started in parallel.

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
