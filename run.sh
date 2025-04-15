#!/bin/bash

docker run --rm \
  -v "$(pwd)/data:/app/data" \
  -e INTERVAL_MINUTES=10 \
  ghcr.io/tna76874/gmapslocation:latest
