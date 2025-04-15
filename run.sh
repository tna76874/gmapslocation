#!/bin/bash

docker run --rm \
  -v "$(pwd)/data:/app/data" \
  ghcr.io/tna76874/gmapslocation:latest
