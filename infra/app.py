#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stacks.base_stack import BaseStack
from stacks.lambdas_stack import LambdasStack
from stacks.auth_stack import AuthStack
from stacks.gateway_stack import GatewayStack

app = cdk.App()
project_prefix = os.environ.get('PROJECT_PREFIX', 'photoagent')
env = cdk.Environment(region=os.environ.get('CDK_DEFAULT_REGION','ap-southeast-2'),
                      account=os.environ.get('CDK_DEFAULT_ACCOUNT', None))

base = BaseStack(app, f"{project_prefix}-Base", env=env, project_prefix=project_prefix)
lambdas = LambdasStack(app, f"{project_prefix}-Lambdas", env=env, base_stack=base, project_prefix=project_prefix)
auth = AuthStack(app, f"{project_prefix}-Auth", env=env, project_prefix=project_prefix)
gateway = GatewayStack(app, f"{project_prefix}-Gateway",
                       env=env,
                       project_prefix=project_prefix,
                       lambda_functions=lambdas.lambda_functions,
                       gateway_invoke_role=base.gateway_invoke_role,
                       cognito_details=auth.get_outputs())
app.synth()
