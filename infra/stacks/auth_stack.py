from aws_cdk import (
    Stack,
    aws_cognito as cognito,
    aws_secretsmanager as secretsmanager
)
from constructs import Construct

class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, project_prefix: str = 'photoagent', **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        self.project_prefix = project_prefix

        self.user_pool = cognito.UserPool(self, "AgentCoreUserPool",
            user_pool_name=f"{project_prefix}-agentcore-up",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True)
        )

        self.user_pool_domain = self.user_pool.add_domain("AgentCoreUserPoolDomain",
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=f"{project_prefix}-agentcore-dev")
        )

        # Add resource server for client credentials scope
        gateway_access_scope = cognito.ResourceServerScope(
            scope_name="gateway.access",
            scope_description="Access to the MCP Gateway"
        )
        
        self.resource_server = self.user_pool.add_resource_server("AgentCoreResourceServer",
            identifier=f"{project_prefix}-api",
            scopes=[gateway_access_scope]
        )

        self.app_client = self.user_pool.add_client("AgentCoreClient",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    client_credentials=True
                ),
                scopes=[
                    cognito.OAuthScope.resource_server(self.resource_server, gateway_access_scope)
                ],
                callback_urls=["https://localhost:3000/callback"],  # Required even if not used
                logout_urls=["https://localhost:3000/logout"]       # Required even if not used
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ]
        )

        self.client_secret_secret = secretsmanager.Secret(self, "AgentCoreClientSecret",
            secret_name=f"{project_prefix}/cognito/client-secret",
            description="Client secret for AgentCore MCP Gateway"
        )

    def get_outputs(self):
        return {
            "user_pool_id": self.user_pool.user_pool_id,
            "app_client_id": self.app_client.user_pool_client_id,
            "client_secret_arn": self.client_secret_secret.secret_arn,
            "user_pool_provider_url": f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool.user_pool_id}"
        }
