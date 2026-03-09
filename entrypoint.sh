#!/bin/bash
set -e

echo "Building GraphGen configuration..."
python3 /app/yaml_builder.py

echo "Starting GraphGen..."
python3 -m graphgen.run --config_file /tmp/graphgen_config.yaml

echo "GraphGen completed successfully!"
