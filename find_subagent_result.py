import json
import os

log_path = "/Users/macbook/.gemini/antigravity-ide/brain/649cf8ee-4f85-4f84-9549-c72b9a0fb4b4/.system_generated/logs/transcript.jsonl"

found = []
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        found.append(line.strip())

# Print the last 20 lines to see what happened after step 191
for line in found[-20:]:
    try:
        data = json.loads(line)
        print(f"Step: {data.get('step_index')} Source: {data.get('source')} Type: {data.get('type')}")
        if data.get('source') == 'SYSTEM' and data.get('type') == 'TOOL_RESPONSE':
            print("Response:", data.get('content')[:500])
        elif data.get('source') == 'MODEL' and data.get('type') == 'PLANNER_RESPONSE':
            for tool in data.get('tool_calls', []):
                print(f"Tool: {tool.get('name')}")
        elif data.get('source') == 'USER_EXPLICIT':
            print("User:", data.get('content'))
    except:
        print("Raw:", line[:200])
