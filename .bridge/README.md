# Bridge — Coordinación Multi-Agente

Este directorio permite que opencode, Claude Code, Gemini (Antigravity) y Codex
se coordinen compartiendo tareas y estado a través del filesystem.

## Protocolo

### Tareas (`.bridge/tasks/`)
```json
{
  "from": "opencode",
  "to": "claude | gemini | codex",
  "type": "implement | review | research",
  "project": "28-whatsapp-restaurant",
  "task": "Descripción",
  "files": ["ruta/archivo.py"],
  "status": "pending | in_progress | done",
  "timestamp": "2026-06-07T..."
}
```

### Estados de archivos modificados
`.bridge/state/` contiene el estado actual del proyecto.
