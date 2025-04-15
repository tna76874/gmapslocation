#!/bin/bash
if ! git diff-index --quiet HEAD --; then
    echo "Es gibt uncomittete Änderungen im Repository. Bitte committen Sie Ihre Änderungen zuerst."
    exit 1
fi

./build.sh Dockerfile
