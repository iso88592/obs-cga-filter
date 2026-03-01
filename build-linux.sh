#!/usr/bin/env bash
set -euo pipefail

IMAGE="obs-cga-filter-builder"
CONTAINER="obs-cga-filter-build"
PLUGIN_DIR="${HOME}/.config/obs-studio/plugins/obs-cga-filter"

echo "==> Building Docker image..."
docker build -t "$IMAGE" .

echo "==> Extracting build artifacts..."
docker rm -f "$CONTAINER" 2>/dev/null || true
docker create --name "$CONTAINER" "$IMAGE"
rm -rf /tmp/obs-cga-output
docker cp "$CONTAINER:/output" /tmp/obs-cga-output
docker rm "$CONTAINER"

echo "==> Installing to $PLUGIN_DIR ..."
mkdir -p "$PLUGIN_DIR/bin/64bit"
cp -v /tmp/obs-cga-output/obs-cga-filter/bin/64bit/obs-cga-filter.so \
      "$PLUGIN_DIR/bin/64bit/"
mkdir -p "$PLUGIN_DIR/data"
cp -rv /tmp/obs-cga-output/obs-cga-filter/data/. \
       "$PLUGIN_DIR/data/"

echo ""
echo "Done. Plugin installed to:"
echo "  $PLUGIN_DIR"
echo ""
echo "Restart OBS and add 'CGA Dither' from the video filter list."
