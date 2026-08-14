#!/usr/bin/env bash

set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly INFRA_DIR="${SCRIPT_DIR}/infra"
readonly BACKEND_CONFIG_INPUT="${BACKEND_CONFIG:-backend.hcl}"
readonly TFVARS_FILE_INPUT="${TFVARS_FILE:-terraform.tfvars}"
readonly BACKEND_CONFIG="$(
  [[ "${BACKEND_CONFIG_INPUT}" = /* ]] \
    && printf '%s' "${BACKEND_CONFIG_INPUT}" \
    || printf '%s/%s' "${INFRA_DIR}" "${BACKEND_CONFIG_INPUT}"
)"
readonly TFVARS_FILE="$(
  [[ "${TFVARS_FILE_INPUT}" = /* ]] \
    && printf '%s' "${TFVARS_FILE_INPUT}" \
    || printf '%s/%s' "${INFRA_DIR}" "${TFVARS_FILE_INPUT}"
)"

export TF_IN_AUTOMATION=true

on_error() {
  local exit_code=$?
  echo "Deployment failed at line ${BASH_LINENO[0]}." >&2
  exit "${exit_code}"
}
trap on_error ERR

for command in aws docker terraform; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Required command not found: ${command}" >&2
    exit 1
  fi
done

if [[ ! -f "${BACKEND_CONFIG}" ]]; then
  echo "Terraform backend configuration not found: ${BACKEND_CONFIG}" >&2
  exit 1
fi

if [[ ! -f "${TFVARS_FILE}" ]]; then
  echo "Terraform variable file not found: ${TFVARS_FILE}" >&2
  exit 1
fi

echo "Checking AWS credentials and Docker."
aws sts get-caller-identity >/dev/null
docker info >/dev/null

echo "Initialising Terraform."
terraform -chdir="${INFRA_DIR}" init \
  -input=false \
  -backend-config="${BACKEND_CONFIG}"

echo "Creating the ECR repository first."
terraform -chdir="${INFRA_DIR}" apply \
  -input=false \
  -auto-approve \
  -var-file="${TFVARS_FILE}" \
  -target=aws_ecr_repository.application

AWS_REGION="$(
  terraform -chdir="${INFRA_DIR}" output -raw aws_region
)"
export AWS_REGION

echo "Building and pushing the latest container image."
"${SCRIPT_DIR}/build.sh"

echo "Deploying the remaining infrastructure."
terraform -chdir="${INFRA_DIR}" apply \
  -input=false \
  -auto-approve \
  -var-file="${TFVARS_FILE}"

ECS_CLUSTER_ARN="$(
  terraform -chdir="${INFRA_DIR}" output -raw ecs_cluster_arn
)"
ECS_SERVICE_NAME="$(
  terraform -chdir="${INFRA_DIR}" output -raw ecs_service_name
)"

echo "Starting a fresh ECS deployment for the latest image."
aws ecs update-service \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER_ARN}" \
  --service "${ECS_SERVICE_NAME}" \
  --force-new-deployment \
  >/dev/null

echo "Waiting for ECS to become stable."
aws ecs wait services-stable \
  --region "${AWS_REGION}" \
  --cluster "${ECS_CLUSTER_ARN}" \
  --services "${ECS_SERVICE_NAME}"

API_URL="$(terraform -chdir="${INFRA_DIR}" output -raw api_gateway_url)"
SLACK_URL="$(terraform -chdir="${INFRA_DIR}" output -raw slack_events_url)"

echo "Deployment completed."
echo "API URL: ${API_URL}"
echo "Slack events URL: ${SLACK_URL}"
