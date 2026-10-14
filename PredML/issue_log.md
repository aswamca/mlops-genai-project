# Issue Log

Issues encountered while running the PredML Docker Compose and MLflow workflow.

## 2026-10-13

### Jenkins WSL agent could not reach the Windows Jenkins controller

- **Symptom:** The Jenkins inbound agent repeatedly tried to connect to
  `http://host.docker.internal:8080/` and logged
  `UnknownHostException: host.docker.internal`. After changing the controller
  port to `8081`, requests from Ubuntu WSL to both `localhost:8081` and the
  Windows host addresses timed out.
- **Cause:** Jenkins was running on Windows at port `8081`, while the agent was
  running under a native Docker Engine inside Ubuntu WSL. In this setup,
  `host.docker.internal` is not automatically resolvable, and Windows'
  inbound firewall did not allow the WSL virtual adapter to reach port `8081`.
  The Docker socket and Jenkins listener were functioning correctly.
- **Resolution:** Confirmed the Windows Jenkins service was running and
  listening on `0.0.0.0:8081`. In elevated Windows PowerShell, added a
  narrowly scoped inbound firewall rule for the WSL adapter:

  ```powershell
  New-NetFirewallRule `
      -DisplayName "Allow Jenkins from WSL" `
      -Direction Inbound `
      -Action Allow `
      -Protocol TCP `
      -LocalPort 8081 `
      -InterfaceAlias "vEthernet (WSL (Hyper-V firewall))" `
      -Profile Any
  ```

  From Ubuntu WSL, verified the controller with:

  ```bash
  curl --fail --connect-timeout 5 http://172.31.176.1:8081/login
  ```

  The response returned the Jenkins sign-in page successfully. The agent
  should use the WSL gateway address and the Jenkins controller's actual port:

  ```bash
  docker rm --force predml-ci-agent 2>/dev/null || true

  docker run --detach \
    --name predml-ci-agent \
    --network host \
    --volume /var/run/docker.sock:/var/run/docker.sock \
    predml-ci:1.0 \
    -url "http://172.31.176.1:8081" \
    -secret "<agent-secret>" \
    -name "predml-ci-agent"
  ```

- **Result:** WSL can reach Jenkins over port `8081`. The agent no longer
  depends on Docker Desktop or an automatically provided
  `host.docker.internal` hostname. The agent secret remains private and must
  be replaced locally rather than committed to the repository.

### Jenkins agent verification and laptop shutdown behavior

- **Verification:** A running `predml-ci-agent` container is not sufficient to
  prove that Jenkins can use it. Confirm the agent logs contain both
  `WebSocket connection open` and `Connected`, confirm the node is **Online**
  at `http://localhost:8081/computer/`, and verify Docker access with:

  ```bash
  docker ps
  docker logs --tail=100 predml-ci-agent
  docker exec predml-ci-agent docker version
  ```

- **Shutdown behavior:** Shutting down or restarting the laptop stops the
  Jenkins Windows service, Ubuntu WSL, and the running agent container. The
  container and `predml-ci:1.0` image remain stored, but the container does not
  automatically reconnect by itself.
- **Resolution:** After Windows Jenkins and Ubuntu WSL are available again,
  restart Docker and the existing agent:

  ```bash
  sudo service docker start
  docker start predml-ci-agent
  docker logs --tail=100 predml-ci-agent
  ```

  If the container was removed, recreate it with the native WSL Docker
  command documented above. If the WSL gateway address changes, recalculate it
  with `ip route` and update the agent URL before recreating the container.

### Jenkins agent could not access the Docker socket

- **Symptom:** The agent connected to Jenkins, but
  `docker exec predml-ci-agent docker version` showed the Docker client and
  then failed with `permission denied` for
  `unix:///var/run/docker.sock`.
- **Cause:** The image runs Jenkins as the non-root `jenkins` user. Mounting
  `/var/run/docker.sock` exposes the socket, but does not automatically add
  the container user to the socket's group.
- **Resolution:** Recreate the agent with the numeric group ID of the WSL
  Docker socket:

  ```bash
  DOCKER_SOCK_GID=$(stat -c '%g' /var/run/docker.sock)

  docker rm --force predml-ci-agent

  docker run --detach \
    --name predml-ci-agent \
    --network host \
    --group-add "$DOCKER_SOCK_GID" \
    --volume /var/run/docker.sock:/var/run/docker.sock \
    predml-ci:1.0 \
    -url "http://172.31.176.1:8081" \
    -webSocket \
    -secret "<agent-secret>" \
    -name "predml-ci-agent"
  ```

- **Verification:** Confirm Docker access as the agent user:

  ```bash
  docker exec predml-ci-agent docker version
  ```

  The command should show both Docker **Client** and **Server** sections
  without a permission error.

### Terraform apply failed to create EventBridge SageMaker schedules

- **Symptom:** Terraform created the IAM roles, ECR repositories, S3 bucket,
  Feature Store group, and SageMaker MLflow tracking server, but both
  EventBridge schedules failed with:
  `Parameters SageMakerPipelineParameters must be specified.`
- **Cause:** Empty `sagemaker_pipeline_parameters` blocks were rendered in the
  EventBridge target. AWS rejected those empty parameter objects because the
  SageMaker pipelines currently have no runtime parameters.
- **Resolution:** Removed the empty `sagemaker_pipeline_parameters` blocks from
  both schedules. Terraform now omits the optional target parameter object so
  SageMaker starts each pipeline with its configured defaults.
- **Next step:** Push the fix and rerun the Terraform pipeline with
  `TF_ACTION=apply`. Terraform should retain the resources already recorded in
  remote state and create the two missing schedules. Review the plan before
  applying if the plan reports any changes beyond those schedules.

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
