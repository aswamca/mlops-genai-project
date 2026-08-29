# Local development notes

This folder is kept as a legacy container for the older local project layout. The active Ollama-specific instructions now live in [GenAI_ollama/README.md](GenAI_ollama/README.md).

Use the Ollama-specific folder for all local setup, reruns, troubleshooting, and secure-RAG guidance.

## Why the Ollama README moved

The local project was split so that the Ollama-specific setup is separated from the broader local ML examples. This keeps the documentation focused on the model runtime, the local API, and the security pattern used for RAG.

## Fastest way to re-run the local Ollama examples

From the project root:

```powershell
cd E:\Projects\mlops-genai-project
. .\.venv\Scripts\Activate.ps1
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_CHAT_MODEL = "llama3.2:1b"
$env:OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"

ollama serve
python "local/GenAI_ollama/src/01_langchain_local.py"
python "local/GenAI_ollama/src/02_rag_local.py"
```

## Do you need to pull Ollama models again after a reboot?

Usually no.

Ollama stores the downloaded models on disk. After a reboot, the models remain installed unless you explicitly delete them or run a fresh install. What typically restarts is the local Ollama service, not the model package itself.

If you reboot and the service is not running, do this:

```powershell
ollama serve
ollama list
```

If you see the model names in `ollama list`, you do not need to run `ollama pull` again. You only pull again if the model is missing, deleted, or the install was corrupted.

## Why the port conflict happens

Ollama binds to port `11434` on localhost. Windows does not allow two processes to use the same port. If a previous `ollama.exe` is still running, a second `ollama serve` call fails with a socket-binding error.

Check the active listener:

```powershell
Get-NetTCPConnection -LocalPort 11434
Get-Process -Name ollama
```

If a process is already alive, leave it running. If you need to restart it, stop the old one first:

```powershell
Stop-Process -Name ollama -Force
ollama serve
```

This is why a reboot can look like a fresh environment even though the model is still installed: the OS may keep a background `ollama.exe` session alive or restart the service automatically.
