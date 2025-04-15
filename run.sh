#!/bin/bash

docker run --rm \
  -v "$(pwd)/data:/app/data" \
  gmapslocation:latest
