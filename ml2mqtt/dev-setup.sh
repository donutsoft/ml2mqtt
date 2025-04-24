#!/bin/bash

mypy app.py --check-untyped-defs

# Customize these
IMAGE_NAME="ml2mqtt"
CONTAINER_NAME="ml2mqtt-dev"
HOST_PORT=5000
CONTAINER_PORT=5000

echo "Building Docker image"
docker build -t $IMAGE_NAME .

# Stop and remove any existing container
if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
  echo "Restarting existing container..."
  docker stop $CONTAINER_NAME
  docker rm $CONTAINER_NAME
fi

echo "Starting dev container with mounted volume..."
docker run -d \
  --name $CONTAINER_NAME \
  -p $HOST_PORT:$CONTAINER_PORT \
  -v "$PWD":/app \
  -e FLASK_ENV=development \
  -w /app \
  $IMAGE_NAME \
  sh -c 'while true; do
    python -m flask run --host=0.0.0.0 &
    pid=$!
    # Wait until a .py file is modified
    inotifywait -e modify $(find . -type f \( -name "*.py" -o -name "*.html" -o -name "*.css" \)) >/dev/null 2>&1
    kill $pid
    wait $pid
  done'

echo "Running at http://localhost:$HOST_PORT"
docker logs -f $CONTAINER_NAME
