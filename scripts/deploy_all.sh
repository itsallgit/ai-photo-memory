#!/usr/bin/env bash
set -euo pipefail
PROFILE=""
PREFIX="${PROJECT_PREFIX:-photoagent}"
REGION="${REGION:-ap-southeast-2}"
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --profile) PROFILE="--profile $2"; shift 2;;
    --prefix) PREFIX="$2"; shift 2;;
    --region) REGION="$2"; shift 2;;
    -h|--help) echo "Usage: $0 [--profile PROFILE] [--prefix PREFIX] [--region REGION]"; exit 0;;
    *) echo "Unknown parameter passed: $1"; exit 1;;
  esac
done
echo "Using profile: $PROFILE"
echo "Project prefix: $PREFIX"
echo "Region: $REGION"
echo "Preparing infra deployment..."
pushd infra >/dev/null
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
export CDK_DEFAULT_REGION="$REGION"
export CDK_DEFAULT_ACCOUNT=$(aws sts get-caller-identity $PROFILE --query Account --output text)
export PROJECT_PREFIX="$PREFIX"
echo "Bootstrapping CDK..."
cdk bootstrap aws://$CDK_DEFAULT_ACCOUNT/$REGION $PROFILE --require-approval never || true
echo "Deploying stacks..."
STACKS=("${PREFIX}-Base" "${PREFIX}-Lambdas" "${PREFIX}-Auth" "${PREFIX}-Gateway")
for S in "${STACKS[@]}"; do
  echo "Deploying $S..."
  cdk deploy "$S" $PROFILE --require-approval never
done
popd >/dev/null
echo "Deploy complete."
