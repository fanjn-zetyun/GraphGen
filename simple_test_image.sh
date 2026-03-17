docker run --rm --name graphgen-test \
  -e GRAPHGEN_PARAMS='{"synthesizer_model":"gpt-4o-mini","synthesizer_url":"https://api.openai.com/v1","api_key":"your-api-key","upload_file":"/workspace/input/test.jsonl","partition_method":"ece","chunk_size":1024,"mode":"aggregated","data_format":"Alpaca"}' \
  -v "$(pwd)/examples/data:/workspace/input:ro" \
  -v "$(pwd)/output:/workspace/user-data/dataset" \
  -v "$(pwd)/logs:/app/container_logs" \
  graphgen-worker:latest
