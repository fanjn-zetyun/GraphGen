docker run --rm --name graphgen-test \
  -e GRAPHGEN_PARAMS='{"tokenizer":"gpt-4o-mini","synthesizer_model":"gpt-4o-mini","synthesizer_url":"https://api.openai.com/v1","api_key":"your-api-key","upload_file":"examples/input_examples/txt_demo.txt","partition_method":"ece","chunk_size":1024,"mode":"aggregated","data_format":"Alpaca"}' \
  registry.hd-02.alayanew.com:8443/alayanew-4fd285c4-c4f3-4e92-80ee-26169717cba8/graphgen:1.0
  

docker run --name graphgen-test \
  -e GRAPHGEN_PARAMS='{"tokenizer":"Qwen/Qwen3-32B","synthesizer_model":"ZGU78dZG4_CZsS1WRwI7l","synthesizer_url":"https://vllm-5V3w0wgP.test.llamafactory.online/v1","api_key":"68b705e0-b16c-46c2-a4eb-44192c1b0fa8","upload_file":"examples/input_examples/txt_demo.txt","partition_method":"ece","chunk_size":1024,"mode":"aggregated","data_format":"Alpaca"}' \
  registry.hd-02.alayanew.com:8443/alayanew-4fd285c4-c4f3-4e92-80ee-26169717cba8/graphgen:1.3

docker run --name graphgen-test \
  -e GRAPHGEN_PARAMS='{"synthesizer_model":"ZGU78dZG4_CZsS1WRwI7l","synthesizer_url":"https://vllm-5V3w0wgP.test.llamafactory.online/v1","api_key":"68b705e0-b16c-46c2-a4eb-44192c1b0fa8","upload_file":"examples/input_examples/txt_demo.txt","partition_method":"ece","chunk_size":1024,"mode":"aggregated","data_format":"Alpaca"}' \
  registry.hd-02.alayanew.com:8443/alayanew-4fd285c4-c4f3-4e92-80ee-26169717cba8/graphgen:1.4

tokenizer
  -v "$(pwd)/examples/data:/workspace/input:ro" \
  -v "$(pwd)/output:/workspace/user-data/dataset" \
  -v "$(pwd)/logs:/app/container_logs" \
  graphgen-worker:latest
