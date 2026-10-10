# Issue Log

Issues encountered while running the PredML Docker Compose and MLflow workflow.

## 2026-10-11

### MLflow rejected requests from the batch container

- **Symptom:** Training failed with HTTP 403 and `Invalid Host header - possible DNS rebinding attack detected` when the batch container contacted `http://mlflow:5000`.
- **Cause:** MLflow 3 validates incoming `Host` headers, and the Compose service hostname was not in its allowed-host list.
- **Resolution:** Added `mlflow:5000` to MLflow's `--allowed-hosts` option in `docker/mlflow.Dockerfile`, then rebuilt and restarted MLflow.
- **Result:** Batch requests to the MLflow service succeeded.

### MLflow UI rejected requests to the loopback address

- **Symptom:** The UI returned `Invalid Host header` when opened through `127.0.0.1:5000`.
- **Cause:** The local loopback address was not in the MLflow allowed-host list.
- **Resolution:** Added `127.0.0.1:5000` and `localhost:5000` to `--allowed-hosts`, then rebuilt and restarted MLflow.
- **Result:** Both local addresses returned HTTP 200.

### Batch inference could not find the champion model artifact

- **Symptom:** Stage 6 failed with `MlflowException: No such artifact: ''`.
- **Cause:** The original `pharmacy_cost_forecasting` experiment had been created with a Windows-local artifact URI (`file:E:/...`). That path is not available inside the Linux containers, and the old champion version's model files were not present in the shared artifacts directory.
- **Resolution:** Enabled MLflow artifact proxying with `--serve-artifacts`, set `--default-artifact-root mlflow-artifacts:/`, and configured the artifact destination as the persisted `/app/PredML/mlruns/artifacts` directory. Docker batch runs use the separate `pharmacy_cost_forecasting_docker` experiment through the `MLFLOW_EXPERIMENT` environment variable. The old experiment and its records were retained.
- **Result:** New Docker-trained artifacts are stored through MLflow's artifact proxy and persist under the host's `PredML/mlruns` directory.

### New model version was not automatically used for inference

- **Symptom:** Stage 5 registered v4 but kept it as a challenger; stage 6 continued failing while trying to load the champion.
- **Cause:** The challenger and champion test MAPE values tied (`0.0112`). The promotion gate only promotes a challenger when it improves on the champion, so the champion alias correctly remained on legacy v3.
- **Resolution:** Reviewed the candidate and explicitly moved the champion alias to v4 with:

  ```powershell
  docker compose -f docker/docker-compose.yml run --rm -e STAGE=10_rollback batch --to-version 4
  ```

- **Result:** The champion alias points to v4, and stage 6 inference runs with its Docker-accessible artifact. The former champion becomes the previous version.

### Git metadata warnings during training

- **Symptom:** MLflow warned that it could not determine the Git SHA, branch, or repository URL.
- **Cause:** The slim batch image does not install the Git executable. These Git details are optional MLflow run metadata.
- **Resolution:** No change was required for training. Install Git in the batch image only if recording Git provenance in MLflow becomes a requirement.
- **Result:** Training, metric logging, and model registration completed despite these warnings.

### Batch container exits while MLflow remains running

- **Symptom:** After a one-off batch run, the MLflow container remained running.
- **Cause:** `docker compose run --rm` removes the one-off batch container after completion; it does not stop service dependencies.
- **Resolution:** This is the intended behavior. Stop MLflow manually when it is no longer needed:

  ```powershell
  docker compose -f docker/docker-compose.yml stop mlflow
  ```

### Non-blocking MLflow model logging deprecation warning

- **Symptom:** MLflow warned that `artifact_path` is deprecated in the model logging call.
- **Cause:** The training code uses the older `artifact_path` argument to `mlflow.xgboost.log_model`.
- **Resolution:** No runtime fix was needed; model logging and registration succeeded. Update to the recommended `name` argument in a future cleanup.
