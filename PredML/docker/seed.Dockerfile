# Snapshot the existing local PredML runtime state for Kubernetes PVC seeding.
FROM alpine:3.20

COPY data /seed/data
COPY mlruns /seed/mlruns
COPY model /seed/model
COPY predictions /seed/predictions
COPY monitoring /seed/monitoring
