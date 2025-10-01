from aws_cdk import (
    Stack,
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
            timeout=_lambda.Duration.seconds(300),
            log_retention=logs.RetentionDays.ONE_WEEK
        )

        gw_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "bedrock-agentcore-control:CreateGateway",
                "bedrock-agentcore-control:CreateGatewayTarget",
                "bedrock-agentcore-control:DescribeGateway",
                "bedrock-agentcore-control:DeleteGateway",
                "bedrock-agentcore-control:UpdateGateway",
                "bedrock-agentcore-control:ListGateways",
                "bedrock-agentcore-control:ListGatewayTargets",
                "bedrock-agentcore-control:DeleteGatewayTarget",
                "iam:PassRole",
                "secretsmanager:GetSecretValue",
                "cognito-idp:DescribeUserPoolClient"
            ],
            resources=["*"]
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

        cr.CustomResource(self, "GatewayManagerResource",
            service_token=provider.service_token,
            properties=props
        )
