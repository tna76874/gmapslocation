#!/bin/bash

# Usage: ./build.sh [DOCKERFILE] [IMAGEAPPEND]

# Setze Variablen
DOCKERFILE=${1:-Dockerfile}
IMAGEAPPEND=${2:-}

# Setze Variablen, falls sie nicht bereits gesetzt sind (nützlich für lokale Ausführung)
: "${GITHUB_REF:=refs/heads/$(git symbolic-ref --short HEAD)}"

REMOTE_URL=$(git config --get remote.origin.url)
# Überprüfe, ob die URL "github.com" enthält
if [[ $REMOTE_URL == *"github.com"* ]]; then
    # Extrahiere den Repository-Namen von der GitHub-URL
    : "${GITHUB_REPOSITORY:=$(git config --get remote.origin.url | sed 's/.*github.com.//;s/.git$//')}"
else
    # Extrahiere den Repository-Namen aus der URL
    : "${GITHUB_REPOSITORY:=$(basename "$REMOTE_URL" .git)}"
fi

COMMIT_HASH=$(cat server/COMMIT_HASH)
CURRENT_DATE=$(date +'%Y%m%d')
CURRENT_DATE_WITH_HOUR=$(date +'%Y%m%d%H')
if [[ $REMOTE_URL == *"github.com"* ]]; then
  IMAGE_NAME="ghcr.io/${GITHUB_REPOSITORY}${IMAGEAPPEND}"
else
  IMAGE_NAME="local/${GITHUB_REPOSITORY}${IMAGEAPPEND}"
fi

# Festlegen des Kanals basierend auf dem Branch
CHANNEL=""
if [ "$GITHUB_REF" == "refs/heads/master" ] || [ "$GITHUB_REF" == "refs/heads/main" ]; then
  CHANNEL="latest"
elif [ "$GITHUB_REF" == "refs/heads/stable" ]; then
  CHANNEL="stable"
fi
echo "CHANNEL ${CHANNEL}"
echo "IMAGE_NAME ${IMAGE_NAME}"

# Funktion zum Bauen des Docker-Images
build_image() {
  TAG=$1
  docker build . --file ${DOCKERFILE} --tag ${IMAGE_NAME}:${TAG}
  echo "Building ${IMAGE_NAME}:${TAG}"
}

# Funktion zum Pushen des Docker-Images
push_image() {
  TAG=$1
  docker push ${IMAGE_NAME}:${TAG}
}

# Build für den stable-Branch
if [ "$CHANNEL" == "stable" ]; then
  build_image "${CHANNEL}-${CURRENT_DATE}"
  build_image "${CHANNEL}-${CURRENT_DATE_WITH_HOUR}"
fi

# Build für den Commit-Hash
build_image "${COMMIT_HASH}"

# Build für den Kanal (falls gesetzt)
if [ -n "$CHANNEL" ]; then
  build_image "${CHANNEL}"
fi

# Push-Operationen nur durchführen, wenn im CI-Umgebung (GitHub Actions)
if [ "$CI" == "true" ]; then
  if [ "$CHANNEL" == "stable" ]; then
    push_image "${CHANNEL}-${CURRENT_DATE}"
    push_image "${CHANNEL}-${CURRENT_DATE_WITH_HOUR}"
  fi

  push_image "${COMMIT_HASH}"

  if [ -n "$CHANNEL" ]; then
    push_image "${CHANNEL}"
  fi
else
  echo "Lokale Ausführung erkannt - Docker-Images werden nicht gepusht."
fi
