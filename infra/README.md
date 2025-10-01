Infra directory: AWS CDK (Python) app that provisions:
  - Cognito User Pool + App Client (client credentials)
  - Two Lambda functions (photo_service, memory_service)
  - AgentCore Gateway via a Lambda-backed Custom Resource (creates gateway + 4 MCP tools)
  - IAM roles and Secrets Manager placeholder for secrets

Note: AgentCore Runtime deployment has been removed for MVP. The orchestrator runs locally.
