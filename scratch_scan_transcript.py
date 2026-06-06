import json
import re

log_path = "/Users/macbook/.gemini/antigravity-ide/brain/649cf8ee-4f85-4f84-9549-c72b9a0fb4b4/.system_generated/logs/transcript.jsonl"

print("Escaneando el transcript completo en busca de IDs de WhatsApp...")

with open(log_path, 'r', encoding='utf-8') as f:
    for line_idx, line in enumerate(f):
        # Encontrar todas las secuencias de 15 a 16 dígitos
        matches = re.finditer(r'\b\d{15,16}\b', line)
        for m in matches:
            num = m.group(0)
            # Ignorar timestamps típicos
            if num.startswith('17807'):
                continue
            # Mostrar contexto
            start = max(0, m.start() - 80)
            end = min(len(line), m.end() + 120)
            snippet = line[start:end]
            print(f"Línea {line_idx} - Encontrado ID: {num}")
            print(f"  Contexto: ...{snippet}...\n")
