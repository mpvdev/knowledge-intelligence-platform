#!/usr/bin/env bash

set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly INFRA_DIR="${SCRIPT_DIR}/infra"
readonly LOCAL_IMAGE="knowledge-intelligence"
readonly IMAGE_TAG="latest"

for command in aws docker terraform; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Required command not found: ${command}" >&2
    exit 1
  fi
done

cd "${SCRIPT_DIR}"

AWS_REGION="${AWS_REGION:-$(terraform -chdir="${INFRA_DIR}" output -raw aws_region)}"
ECR_REPOSITORY_URL="$(terraform -chdir="${INFRA_DIR}" output -raw ecr_repository_url)"
ECR_REGISTRY="${ECR_REPOSITORY_URL%%/*}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"
REMOTE_IMAGE="${ECR_REPOSITORY_URL}:${IMAGE_TAG}"

echo "Building ${REMOTE_IMAGE} for ${DOCKER_PLATFORM}"
docker build \
  --platform "${DOCKER_PLATFORM}" \
  --tag "${LOCAL_IMAGE}:${IMAGE_TAG}" \
  --tag "${REMOTE_IMAGE}" \
  .

echo "Authenticating to ${ECR_REGISTRY}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Pushing ${REMOTE_IMAGE}"
docker push "${REMOTE_IMAGE}"

echo "Published ${REMOTE_IMAGE}"
echo "Force a new ECS deployment to make the service pull the updated latest image."
