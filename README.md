# PhotoAgent — Strands Nova Voice Assistant (forked + infra)

> This repository started from: `aws-samples/sample-aws-strands-nova-voice-assistant` and has been extended as a PhotoAgent proof-of-concept:
>
> * kept the original frontend / Nova Sonic integration (unchanged)
> * removed the original specialized agents (EC2 / SSM / Backup) — the orchestrator is repurposed
> * added a CDK-based infra folder that provisions two Lambda services, Cognito, an AgentCore Gateway (MCP), and an AgentCore Runtime for the orchestrator
> * added a `deploy_all.sh` script to provision everything end-to-end into a single AWS account (Sydney region `ap-southeast-2` by default)

---

## What changed (summary)

**Removed from original sample**

* Specialized agents `ec2_agent.py`, `ssm_agent.py`, `backup_agent.py` were removed from the `backend` agents folder to keep the repo focused on the PhotoAgent use-case. A backup copy of the original orchestrator is preserved as `orchestrator.py.orig` (if present).

**Added**

* `infra/` — AWS CDK (Python) app to provision the cloud infrastructure:

  * `BaseStack` — IAM roles, SecretsManager placeholder
  * `LambdasStack` — two Lambda services:

    * `photo_service` — two operations exposed as MCP tools: `photo_service.start_slideshow` and `photo_service.get_tags`
    * `memory_service` — two operations exposed as MCP tools: `memory_service.remember` and `memory_service.add_memory`
  * `AuthStack` — Cognito User Pool + App Client (client credentials only)
  * `GatewayStack` — Lambda-backed custom resource that creates/upserts the AgentCore Gateway and registers the 4 MCP tools (one tool per operation)
  * `RuntimeStack` — builds orchestrator Docker image and registers an AgentCore Runtime (custom resource)
  * `custom_resources/gateway_manager/handler.py` — provider Lambda used by the `GatewayStack` and `RuntimeStack` custom resources to call the AgentCore control plane
  * `lambda_src/` — stub Lambda handlers for `photo_service` and `memory_service`
  * `orchestrator/photo_orchestrator.py` — replacement orchestrator that knows how to get tokens from Cognito and call the Gateway’s `tools/list` and `tools/call` endpoints
* `scripts/deploy_all.sh` — single idempotent script to build & deploy all infra into your account. Supports environment variables and flags to specify AWS profile, project prefix, and region.

---

## Directory structure (high level)

```
<repo-root>/
├── backend/                          # original backend (kept from sample repo)
│   └── src/.../agents/
│       ├── orchestrator.py.orig      # original orchestrator (backed up)
│       └── photo_orchestrator.py     # new orchestrator (added)
├── frontend/                         # original frontend (kept unchanged)
├── infra/                            # CDK app (new)
│   ├── app.py
│   ├── cdk.json
│   ├── requirements.txt
│   ├── stacks/
│   │   ├── base_stack.py
│   │   ├── lambdas_stack.py
│   │   ├── auth_stack.py
│   │   ├── gateway_stack.py
│   │   └── runtime_stack.py
│   ├── lambda_src/
│   │   ├── photo_service/handler.py
│   │   └── memory_service/handler.py
│   └── custom_resources/
│       └── gateway_manager/handler.py
├── scripts/
│   └── deploy_all.sh
├── README.md                          # THIS FILE (updated)
└── README_PHOTOAGENT.md               # supplemental notes
```

---

## Prerequisites (local machine)

Before you deploy, ensure the following are installed:

* Git
* Python 3.12+ (required for smithy-aws-core dependency)
* pip
* Node.js 16+ and npm
* AWS CLI (configured with credentials or environment variables)
* Docker (for building the orchestrator image)
* AWS CDK v2 (install with `npm install -g aws-cdk`)
* `jq` (recommended for CLI JSON parsing in examples; optional)

Make sure your AWS account/role has permissions to create IAM roles, Lambda functions, ECR repositories, Cognito User Pools, and CloudFormation stacks. Also check that AgentCore (Bedrock AgentCore) APIs are available in the selected region¸ in your account — if the control-plane for AgentCore isn’t available the `GatewayStack` and `RuntimeStack` custom resources will fail.

---

## Quick glossary

* **Gateway (AgentCore Gateway)**: managed front door that exposes tools via the Model Context Protocol (MCP). We use a Gateway to register each Lambda operation as an MCP tool.
* **Tool**: an MCP tool — a JSON-schema described endpoint that models can call via `tools/call`.
* **Custom resource**: small Lambda code that calls the AgentCore control-plane APIs during CloudFormation deployment to create gateway/targets/runtime (idempotent upsert behaviour).

---

## Deployment walkthrough — full step-by-step

> This section gives exact commands and verifies the deployment end-to-end. The example uses:
>
> * AWS profile `exalm` (replace with your profile)
> * project prefix `photoagent` (you can override)
> * region `us-east-1`

### 1) Application Backend Setup

Clone and prepare the environment:

```bash
# Clone the repository
git clone <repository-url>
cd sample-aws-strands-nova-voice-assistant

# Check Python version (must be 3.12+)
python --version

# Assuming you're using pyenv...
# pyenv versions
# pyenv install --list | grep "3.12"
# pyenv install 3.12.7
# pyenv global 3.12.7

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows

# Install Python dependencies
pip install -r requirements.txt
```

> Note: If you get an ERROR: Failed building wheel for pyaudio due to "portaudio.h" not being found, this is a common issue on macOS where portaudio needs to be installed as a system dependency before pyaudio can be compiled. 
> run the following the retry installing requirements:
> `brew install portaudio`

### 2) Verify prerequisites

Confirm the tools are installed:

```bash
python --version  # Should show 3.12.x or higher
node --version
npm --version
docker --version
aws --version
cdk --version
```

If any are missing, install them before proceeding.

### 3) Configure AWS Service Authentication

This application uses two different AWS authentication mechanisms:

Nova Sonic Integration: Requires AWS credentials as environment variables Other AWS Services: Uses boto3 with AWS profiles.

**Configure AWS CLI profile for other services:**

```bash
aws configure --profile <your-profile-name>
# Enter your AWS Access Key ID, Secret Access Key, and default region
```

Verify AWS identity:

```bash
aws sts get-caller-identity --profile $AWS_PROFILE --region $REGION
```

**Configure Environment Variables File**

Create a `.env` file in the project root (this file is git-ignored for security):

```bash
# Copy the example file and customize
cp .env.example .env
```

Edit `.env` with your AWS profile and region:

```bash
# AWS Configuration
AWS_PROFILE=<> 
AWS_DEFAULT_REGION=us-east-1 # region must have nova sonic model availability

# AWS User
AWS_ACCESS_KEY_ID=<>
AWS_SECRET_ACCESS_KEY=<>

# Voice Assistant Configuration
BYPASS_TOOL_CONSENT=true
```

The `run_backend.sh` script will automatically load these variables.

**Apply the required IAM permissions to your AWS user/role:**

* Amazon Bedrock model invocation
* Supporting services (KMS, STS)
* <TODO>

Create new policy and attach to user (directly or via group):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "BedrockPermissions",
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:GetFoundationModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        },
        {
            "Sid": "SupportingPermissions",
            "Effect": "Allow",
            "Action": [
                "kms:DescribeKey",
                "sts:GetCallerIdentity"
            ],
            "Resource": "*"
        }
    ]
}
```

**Test Environment and AWS Access**

From the project root directory, you can run the following test script to confirm your environment and AWS acces.

```bash
sh scripts/test_aws_access.sh
```

### 4) Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install
```

### 5) Launch the Application

Start the backend server:

```bash
# From the project root (recommended)
./run_backend.sh

# Or with custom parameters:
./run_backend.sh --profile <your-profile> --region <your-region> --voice matthew
```

Start the frontend in a new terminal:

```bash
# Development mode (recommended)
./run_frontend.sh

# Or manually:
cd frontend
npm start
```

---
Below this line has not been tested...
---

### 4) Run the single deploy script

From the repository root (the folder that contains `scripts/deploy_all.sh`):

Option A — env vars already set:

```bash
./scripts/deploy_all.sh
```

Option B — pass flags:

```bash
./scripts/deploy_all.sh --profile dev --prefix photoagent --region ap-southeast-2
```

What the script does:

* Creates a Python virtualenv in `infra/` and installs CDK dependencies
* Bootstraps CDK (if required) into your account/region
* Builds and deploys the stacks:

  * `<prefix>-Base`
  * `<prefix>-Lambdas`
  * `<prefix>-Auth`
  * `<prefix>-Gateway`
  * `<prefix>-Runtime`
* Each stack is deployed incrementally; repeated runs are efficient (CDK updates only changed resources).

**Important**: CDK will build the orchestrator Docker image (requires Docker). It will also call the custom resource that attempts to create/upsert the AgentCore Gateway and Runtime; those API calls require the AgentCore control-plane to be available in the region.

### 5) Wait for `cdk deploy` to complete

Watch the script output. The deploy succeeds when each stack shows `CREATE_COMPLETE` or `UPDATE_COMPLETE`.

If a stack fails, CloudFormation will indicate which resource and you can inspect logs (see Troubleshooting below).

---

## Post-deploy verification — manual checks & how to call the tools

After the deploy completes, we will:

1. locate the Cognito hosted domain, client id and client secret
2. obtain an OAuth client-credentials token
3. find the AgentCore Gateway URL
4. call `/tools/list` and `/tools/call` endpoints to verify the 4 tools

> NOTE — the custom resources use the AgentCore control-plane APIs; depending on service availability in your region, some of these steps may require console inspection (instructions cover both CLI and console options).

### 5.1 Find Cognito App client id & secret and hosted domain

The CDK `AuthStack` created a Cognito User Pool and an App Client that has a generated secret. We need the **Client ID**, **Client Secret**, and the **Hosted Domain** to obtain an access token.

**Recommended (Console) — easiest / most reliable**

* Open the AWS Console → Cognito → User Pools
* Locate the User Pool named like: `<PROJECT_PREFIX>-agentcore-up` (e.g. `photoagent-agentcore-up`)
* Choose **App clients** → find the client named `AgentCoreClient` → click **Show client secret** to reveal the secret
* Choose **App integration** → **Domain name** → note the domain prefix (hosted domain). The token endpoint will be:

  ```
  https://<YOUR_DOMAIN>.auth.ap-southeast-2.amazoncognito.com/oauth2/token
  ```

**Alternative (CLI)**
You can try to retrieve via AWS CLI:

```bash
# Replace PROFILE and REGION if needed
PROFILE=dev
REGION=ap-southeast-2
PREFIX=photoagent

# Get the user pool id (searching by name)
POOL_ID=$(aws cognito-idp list-user-pools --max-results 60 --profile $PROFILE --region $REGION \
  --query "UserPools[?contains(Name, \`${PREFIX}-agentcore-up\`)].Id" --output text)

# Get the client id (this may vary, but usually there will be one client)
CLIENT_ID=$(aws cognito-idp list-user-pool-clients --user-pool-id $POOL_ID --profile $PROFILE --region $REGION \
  --query "UserPoolClients[?starts_with(ClientName, 'AgentCoreClient')].ClientId" --output text)

# Describe client (attempt to output the secret — if available)
aws cognito-idp describe-user-pool-client --user-pool-id $POOL_ID --client-id $CLIENT_ID --profile $PROFILE --region $REGION --output json
```

> If the CLI output doesn't show the client secret (Cognito sometimes only shows it at creation time in certain APIs), open the Cognito Console to reveal the secret. Using the console is the most reliable method.

### 5.2 Obtain OAuth token (client credentials)

Once you have the domain, client id, and client secret, request an access token:

```bash
COGNITO_DOMAIN="<your-domain-prefix>" # e.g. photoagent-agentcore-dev
TOKEN_URL="https://${COGNITO_DOMAIN}.auth.ap-southeast-2.amazoncognito.com/oauth2/token"

# Use HTTP Basic auth with client_id:client_secret
CLIENT_ID="<the-client-id>"
CLIENT_SECRET="<the-client-secret>"

# Request token (returns JSON with access_token)
TOKEN_RESPONSE=$(curl -s -X POST "$TOKEN_URL" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -u "${CLIENT_ID}:${CLIENT_SECRET}" \
  -d "grant_type=client_credentials")

echo "$TOKEN_RESPONSE" | jq .
ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r .access_token)
echo "Access token: $ACCESS_TOKEN"
```

If the command fails, double-check domain, client id/secret, and network connectivity.

### 5.3 Find the AgentCore Gateway URL (where MCP endpoints are served)

Because the Gateway was created by a CloudFormation custom resource, the Gateway control-plane response contains the Gateway ID and `gatewayUrl`. The gateway URL is needed to call `/tools/list` and `/tools/call`.

**Ways to find the Gateway URL**

1. **CloudWatch logs for the Gateway custom resource provider:**

   * Open CloudWatch Logs in the console and search for the log group created for the custom resource Lambda (look for a name containing `GatewayManagerHandler` or `<PREFIX>-Gateway`).
   * Inspect recent logs for lines like `Created gateway id=...` or `describe_gateway` results that include `gatewayUrl`.
   * The provider logs will typically print the `gatewayUrl`.

2. **CloudFormation custom resource event output:**

   * Open CloudFormation console → Stack `<PROJECT_PREFIX>-Gateway` → Resources → find the custom resource (name like `GatewayManagerResource`).
   * The custom resource response may include data; inspect stack events/outputs for hints of Gateway ID/URL.

3. **AgentCore Console (if available in your account):**

   * If AgentCore has a console page in your AWS account, inspect the Gateways page to find the created Gateway and its endpoint URL.

4. **CLI (if the `bedrock-agentcore-control` client is available in your CLI):**

   * There may be CLI calls such as `aws bedrock-agentcore-control list-gateways` then `describe-gateway` — if your AWS CLI supports this API. If present, these commands are the most direct.

Once you have the gateway URL, assign:

```bash
GATEWAY_URL="https://<your-gateway-url>"
```

### 5.4 Call `/tools/list` to verify the four tools are registered

Now call the Gateway `/tools/list` endpoint:

```bash
curl -s -X GET "$GATEWAY_URL/tools/list" -H "Authorization: Bearer $ACCESS_TOKEN" | jq .
```

You should see entries for:

* `photo_service.start_slideshow`
* `photo_service.get_tags`
* `memory_service.remember`
* `memory_service.add_memory`

Each entry should include `inputSchema` and `outputSchema`.

### 5.5 Call a tool (examples)

**1) Get tags (photo_service.get_tags)**

```bash
curl -s -X POST "$GATEWAY_URL/tools/call" \
 -H "Authorization: Bearer $ACCESS_TOKEN" \
 -H "Content-Type: application/json" \
 -d '{"name":"photo_service.get_tags","arguments":{}}' | jq .
```

Expected response (stub):

```json
{
  "tags": [
    {"tag": "beach", "count": 120},
    {"tag": "family", "count": 45},
    {"tag": "sunset", "count": 78}
  ]
}
```

**2) Start slideshow (photo_service.start_slideshow)** — simplified example:

```bash
curl -s -X POST "$GATEWAY_URL/tools/call" \
 -H "Authorization: Bearer $ACCESS_TOKEN" \
 -H "Content-Type: application/json" \
 -d '{"name":"photo_service.start_slideshow","arguments":{"query":{"tags":["beach","sunset"],"date":"2025-09-01"},"settings":{"interval":20}}}' | jq .
```

Expected response (stub):

```json
{
  "message": "Slideshow started (id: <uuid>)",
  "code": 0
}
```

**3) Remember (memory_service.remember) — parse a freeform memory transcript**

```bash
curl -s -X POST "$GATEWAY_URL/tools/call" \
 -H "Authorization: Bearer $ACCESS_TOKEN" \
 -H "Content-Type: application/json" \
 -d '{"name":"memory_service.remember","arguments":{"text":"I took Mum to Bondi Beach last weekend and we saw the sunset."}}' | jq .
```

Expected (stub) response:

```json
{
  "memory_id": "<uuid>",
  "who": ["Alice","Bob"],
  "what": "I took Mum to Bondi Beach last weekend...",
  "when": "2025-09-20",   # example ISO date
  "where": "123 Example St, Sydney, Australia"
}
```

**4) Add memory (memory_service.add_memory)**

```bash
curl -s -X POST "$GATEWAY_URL/tools/call" \
 -H "Authorization: Bearer $ACCESS_TOKEN" \
 -H "Content-Type: application/json" \
 -d '{"name":"memory_service.add_memory","arguments":{"who":["Alice"],"what":"Went to the café","when":"2025-09-20","where":"50 Pitt St, Sydney"}}' | jq .
```

Expected response (stub):

```json
{
  "memory_id": "<uuid>",
  "who": ["Alice"],
  "what": "Went to the café",
  "when": "2025-09-20",
  "where": "50 Pitt St, Sydney"
}
```

If these calls succeed and produce stubbed responses, your Gateway and Lambdas are working end-to-end.

---

## Running the orchestrator locally (optional)

If you want to run the orchestrator locally (instead of in AgentCore Runtime):

1. Set environment variables so the orchestrator can get tokens and talk to the Gateway:

```bash
export GATEWAY_URL="$GATEWAY_URL"
export COGNITO_TOKEN_URL="$TOKEN_URL"
export OAUTH_CLIENT_ID="$CLIENT_ID"
export OAUTH_CLIENT_SECRET="$CLIENT_SECRET"
```

2. Run the orchestrator script (path may vary depending on sample repo layout):

```bash
# from repo root; adjust path if necessary
python backend/src/voice_based_aws_agent/agents/photo_orchestrator.py
```

The orchestrator contains helper functions to call `/tools/list` and `/tools/call`. Running it locally is useful for debugging orchestration logic before deploying the orchestrator into AgentCore Runtime.

---

## Tear down / cleanup

To remove the provisioned stacks, run:

```bash
cd infra
source .venv/bin/activate
cdk destroy --all --profile $AWS_PROFILE --region $REGION
```

Also delete any remaining resources that might not be removed automatically (ECR images, secrets, S3 buckets if you created any manually). If you created any EC2 instances for testing, terminate them.

---

## Troubleshooting

**Stack failed during deploy**

* Open CloudFormation console → the failed stack → Events
* Identify the failing resource (often the custom resource for Gateways or Runtime). Inspect CloudWatch logs for the custom resource provider Lambda (log group name will include `GatewayManagerHandler` or similar).
* Typical causes:

  * AgentCore control-plane APIs not available in the region — the custom resource will error when attempting `create_gateway` etc.
  * IAM permission missing — ensure the deployer has sufficient privileges for Lambda, CloudFormation, Cognito, ECR, and the AgentCore control-plane.

**Cannot retrieve Cognito client secret with CLI**

* Use the Cognito Console to reveal the client secret (App clients → show client secret). The console always allows you to view it.

**Gateway URL missing**

* Look in CloudWatch logs for the GatewayManager provider Lambda to find `describe_gateway` results; the provider logs the `gatewayUrl` after create.
* Or open CloudFormation stack resources and inspect the custom resource details / events.

**Tools not found in `/tools/list`**

* Confirm the Gateway custom resource completed successfully and that it created targets for all 4 tools (see custom resource logs for `create_gateway_target` messages).
* If targets were not created, inspect provider logs to see why (bad schema, API error, missing lambda arn).

---

## Development workflow & notes for team members

* Each developer should run `scripts/deploy_all.sh` from their own AWS account/profile, using a unique `PROJECT_PREFIX` to avoid name collisions (e.g. `photoagent-jane`).
* The CDK stacks are idempotent — repeated `cdk deploy` runs update only changed resources.
* When iterating on Lambda code, update the code under `infra/lambda_src/*` and re-run `cdk deploy <prefix>-Lambdas` to update functions.

---

## Security notes & follow-ups (future hardening)

*  The starter uses permissive IAM policies in some custom resource provider roles for simplicity. For production, lock down IAM permissions to least privilege.
*  Gateways and tools are created with basic auth flows; later steps should include:

  * storing secrets securely in Secrets Manager and rotating them
  * enabling more granular tool-level ACLs
  * adding CloudWatch/X-Ray / OpenTelemetry tracing in Lambdas and orchestrator
*  Network hardening (VPC placement, PrivateLink) if your lambdas or APIs must remain private.

---

## Where to get help

If you hit issues, collect:

* CloudFormation stack events & errors
* CloudWatch logs for the custom resource provider lambda
* Lambda logs for the photo_service and memory_service functions
* Outputs or logs you saw from the deploy script

Share those snippets and I’ll help debug step-by-step.

---

## Appendix — quick check list (copy for your deploy)

1. Unzip merged repo and `cd` to repo root.
2. Confirm prerequisites: Python, Node, Docker, CDK, AWS CLI.
3. Set `AWS_PROFILE`, `PROJECT_PREFIX=photoagent`, `REGION=ap-southeast-2`.
4. Run `./scripts/deploy_all.sh` (or `./scripts/deploy_all.sh --profile dev --prefix photoagent --region ap-southeast-2`).
5. After deploy:

   * Get Cognito app client id & secret (Cognito console)
   * Get Cognito hosted domain (console)
   * Obtain token with client credentials
   * Locate Gateway URL from CloudWatch logs for the `GatewayManagerHandler` or CloudFormation custom resource
   * Call `GET $GATEWAY_URL/tools/list` and `POST $GATEWAY_URL/tools/call` as shown above
6. If any step fails, check CloudFormation events and CloudWatch logs for details.