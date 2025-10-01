from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

class BaseStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, project_prefix: str = 'photoagent', **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        self.project_prefix = project_prefix

        # Role for Lambdas to execute
        self.lambda_execution_role = iam.Role(self, "LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            role_name=f"{project_prefix}-lambda-execution-role",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Role that AgentCore Gateway will assume to invoke Lambdas
        self.gateway_invoke_role = iam.Role(self, "GatewayInvokeRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                iam.ServicePrincipal("bedrock.amazonaws.com")
            ),
            role_name=f"{project_prefix}-gateway-invoke-role"
        )

        # Allow invoke; will be restricted later
        self.gateway_invoke_role.add_to_policy(iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=["*"]
        ))

        # Secrets Manager secret placeholder for Cognito client secret
        self.cognito_client_secret = secretsmanager.Secret(self, "CognitoClientSecret",
            secret_name=f"{project_prefix}/cognito/client-secret",
            description="Cognito App Client secret for AgentCore Gateway integration"
        )
