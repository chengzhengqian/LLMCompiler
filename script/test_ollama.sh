curl -N http://localhost:11434/api/chat -d '{
  "model": "qwen3.8:27b",
  "messages": [{"role": "user", "content": "count to twenty"}]
}'
