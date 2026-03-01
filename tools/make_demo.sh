#!/usr/bin/env bash
# Build the demo Docker image and generate CGA-dithered demo images.
# Output images are written to demo/ in the project root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="obs-cga-demo"

echo "Building Docker image: $IMAGE_NAME ..."
docker build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/Dockerfile.demo" "$PROJECT_ROOT"

echo "Generating demo images ..."
docker run --rm \
    -v "$PROJECT_ROOT":/project \
    "$IMAGE_NAME"

echo "Done. Images are in demo/."
