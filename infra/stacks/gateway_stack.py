from aws_cdk import (
    Stack,
    Duration,
    CustomResource,
    aws_lambda as _lambda,
    aws_iam as iam,
    custom_resources as cr,
    aws_logs as logs
)
from constructs import Construct
import os

class GatewayStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, lambda_functions: dict, gateway_invoke_role: iam.Role, cognito_details: dict, project_prefix: str = 'photoagent', **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        self.project_prefix = project_prefix

        handler_dir = os.path.join(os.getcwd(), "custom_resources", "gateway_manager")
        gw_lambda = _lambda.Function(self, "GatewayManagerHandler",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset(handler_dir),
            timeout=Duration.seconds(300),
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        # Add required permissions for Bedrock AgentCore operations
        gw_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "bedrock-agentcore:CreateGateway",
                "bedrock-agentcore:DeleteGateway",
                "bedrock-agentcore:DescribeGateway",
                "bedrock-agentcore:ListGateways",
                "bedrock-agentcore:CreateGatewayTarget",
                "bedrock-agentcore:DeleteGatewayTarget",
                "bedrock-agentcore:ListGatewayTargets",
                "bedrock-agentcore:UpdateGateway",
                "bedrock-agentcore:UpdateGatewayTarget",
                "bedrock-agentcore:CreateWorkloadIdentity",
                "bedrock-agentcore:DeleteWorkloadIdentity",
                "bedrock-agentcore:ListWorkloadIdentities"
            ],
            resources=["*"]
        ))

        # Add permission to pass the gateway invoke role to Bedrock
        gw_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["iam:PassRole"],
            resources=[gateway_invoke_role.role_arn]
        ))

        # Add permission to read Cognito client secret
        gw_lambda.add_to_role_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["secretsmanager:GetSecretValue"],
            resources=[cognito_details.get("client_secret_arn")]
        ))

        provider = cr.Provider(self, "GatewayManagerProvider", on_event_handler=gw_lambda)

        lambda_arns = {k: v.function_arn for k, v in lambda_functions.items()}

        props = {
            "GatewayName": f"{project_prefix}-gateway",
            "LambdaArns": lambda_arns,
            "GatewayInvokeRoleArn": gateway_invoke_role.role_arn,
            "CognitoUserPoolId": cognito_details.get("user_pool_id"),
            "CognitoAppClientId": cognito_details.get("app_client_id"),
            "CognitoClientSecretArn": cognito_details.get("client_secret_arn"),
            "Region": self.region,
            "ProjectPrefix": project_prefix
        }

        CustomResource(self, "GatewayManagerResource",
            service_token=provider.service_token,
            properties=props
        )
