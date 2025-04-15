#!/bin/bash

INTERVAL=${1:-5}

docker run --rm \
  -v "$(pwd)/data:/app/data" \
  -e INTERVAL_MINUTES="$INTERVAL" \
  ghcr.io/tna76874/gmapslocation:latest