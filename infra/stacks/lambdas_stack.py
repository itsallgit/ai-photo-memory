from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    Duration
)
from constructs import Construct
import os

class LambdasStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, base_stack: object, project_prefix: str = 'photoagent', **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        self.project_prefix = project_prefix
        self.base_stack = base_stack

        handler_dir = os.path.join(os.getcwd(), "lambda_src")

        # Photo service Lambda
        self.photo_service = _lambda.Function(self, "PhotoServiceFunction",
            function_name=f"{project_prefix}-photo-service",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="photo_service.handler",
            code=_lambda.Code.from_asset(os.path.join(handler_dir, "photo_service")),
            timeout=Duration.seconds(30),
            role=self.base_stack.lambda_execution_role
        )

        # Memory service Lambda
        self.memory_service = _lambda.Function(self, "MemoryServiceFunction",
            function_name=f"{project_prefix}-memory-service",
            runtime=_lambda.Runtime.PYTHON_3_10,
            handler="memory_service.handler",
            code=_lambda.Code.from_asset(os.path.join(handler_dir, "memory_service")),
            timeout=Duration.seconds(30),
            role=self.base_stack.lambda_execution_role
        )

        self.lambda_functions = {
            "photo_service": self.photo_service,
            "memory_service": self.memory_service
        }

        # Grant the gateway invoke role permission to invoke these lambdas
        for fn in self.lambda_functions.values():
            fn.grant_invoke(self.base_stack.gateway_invoke_role)
