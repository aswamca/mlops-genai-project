# PredML Kubernetes setup

These manifests run the **locally built Docker images** from `../docker/`:

- `predml-local/mlflow:latest`
- `predml-local/api:latest`
- `predml-local/batch:latest`

Kubernetes does not build these images. Build them first from the `PredML`
directory:

```powershell
docker compose -f docker/docker-compose.yml build
```

For Docker Desktop Kubernetes, the cluster normally shares its local image
store. With Minikube or kind, load the images into that cluster after building
them (for example, use `minikube image load predml-local/api:latest` or
`kind load docker-image predml-local/api:latest`; repeat for all three).

## Apply the infrastructure

Run from the `PredML` directory. Apply the namespace first, then the remaining
manifests:

```powershell
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-pvc.yaml
kubectl apply -f k8s/10-mlflow-deployment.yaml
kubectl apply -f k8s/11-mlflow-service.yaml
```

Wait for MLflow, then populate `predml-data-pvc` through your cluster's storage
workflow with the files from `PredML/data` (including the raw CSV and
`product_master.json`). Run preprocessing and feature-store stages against that
PVC before training. The training Job below expects
`data/03_features_store/offline/features.parquet` to exist already:

```powershell
kubectl apply -f k8s/30-batch-job-train.yaml
kubectl -n predml logs -f job/predml-batch-train
```

After training, run the model-registration stage (`STAGE=05_register_model`)
as a separate batch Job to promote a champion. Then start the realtime API:

```powershell
kubectl apply -f k8s/20-api-deployment.yaml
kubectl apply -f k8s/21-api-service.yaml
kubectl apply -f k8s/22-api-hpa.yaml
```

Create the monitoring baseline and at least one batch prediction before
enabling the scheduled monitor. Then apply:

```powershell
kubectl apply -f k8s/31-batch-cronjob-monitor.yaml
```

For other batch stages (preprocessing, feature-store generation, registration,
batch inference, or baseline creation), make a separate Job from the batch
image and set `STAGE` to a script shipped in that image. The raw-data generator
is deliberately excluded; generate or provide raw inputs outside Kubernetes.

## Local access and status

```powershell
kubectl -n predml get pods,svc,pvc
```

In separate terminals, forward each service explicitly on IPv4 and leave the
commands running:

```powershell
kubectl -n predml port-forward --address 127.0.0.1 service/predml-api 8000:8000
kubectl -n predml port-forward --address 127.0.0.1 service/mlflow 5000:5000
```

Open the API at `http://127.0.0.1:8000` and the MLflow UI at
`http://127.0.0.1:5000`. The API pod requires a registered champion model and
the online feature file before it can become Ready.

The PVCs use `ReadWriteOnce`, suitable for a local/single-node development
cluster. Select shared `ReadWriteMany` storage before scheduling these shared
volumes across nodes in a multi-node cluster. The API HPA also requires Metrics
Server to be installed in the cluster.
