import json
import boto3
import logging
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_client(region):
    return boto3.client('bedrock-agentcore-control', region_name=region)

def cognito_jwks_and_issuer(region, user_pool_id):
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    jwks_uri = issuer + "/.well-known/jwks.json"
    return issuer, jwks_uri

def create_or_update_gateway(event, context):
    props = event['ResourceProperties']
    region = props.get('Region')
    client = get_client(region)
    gateway_name = props.get('GatewayName')
    role_arn = props.get('GatewayInvokeRoleArn')
    user_pool_id = props.get('CognitoUserPoolId')
    app_client_id = props.get('CognitoAppClientId')

    issuer, jwks_uri = cognito_jwks_and_issuer(region, user_pool_id)

    # Check for existing gateway
    existing = None
    try:
        resp = client.list_gateways()
        for g in resp.get('items', []):
            if g.get('name') == gateway_name:
                existing = g
                break
    except ClientError as e:
        logger.info(f'list_gateways failed: {e}')
        existing = None

    if existing:
        gateway_id = existing['gatewayId']
        logger.info(f"Found existing gateway id={gateway_id}, skipping create.")
    else:
        create_resp = client.create_gateway(
            name=gateway_name,
            protocolType='MCP',
            roleArn=role_arn,
            authorizerType='CUSTOM_JWT',
            authorizerConfiguration={
                'customJWTAuthorizer': {
                    'discoveryUrl': f"{issuer}/.well-known/openid-configuration",
                    'allowedAudience': [app_client_id],
                    'allowedClients': [app_client_id]
                }
            }
        )
        gateway_id = create_resp['gatewayId']
        logger.info(f"Created gateway id={gateway_id}")

    # Define tool schemas and map to lambdas
    lambda_arns = props.get('LambdaArns', {})
    photo_start_schema = { "name":"photo-service.start-slideshow", "description":"Start a slideshow matching criteria", "inputSchema":{"type":"object","properties":{"query":{"type":"object","properties":{"tags":{"type":"array","items":{"type":"string"}},"date":{"type":"string"},"year":{"type":"integer"},"month":{"type":"string"}}},"settings":{"type":"object","properties":{"interval":{"type":"integer"}}}}}, "outputSchema":{"type":"object","properties":{"message":{"type":"string"},"code":{"type":"integer"}}} }
    photo_get_tags_schema = { "name":"photo-service.get-tags", "description":"Return available tags and optional counts", "inputSchema":{"type":"object","properties":{}}, "outputSchema":{"type":"object","properties":{"tags":{"type":"array","items":{"type":"object","properties":{"tag":{"type":"string"},"count":{"type":"integer"}}}}}} }
    memory_remember_schema = { "name":"memory-service.remember", "description":"Accept a freeform memory string and return structured memory", "inputSchema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}, "outputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"who":{"type":"array","items":{"type":"string"}},"what":{"type":"string"},"when":{"type":"string"},"where":{"type":"string"}},"required":["memory_id","what"]} }
    memory_add_schema = { "name":"memory-service.add-memory", "description":"Store structured memory (who/what/when/where)", "inputSchema":{"type":"object","properties":{"who":{"type":"array","items":{"type":"string"}},"what":{"type":"string"},"when":{"type":"string"},"where":{"type":"string"}},"required":["what"]}, "outputSchema":{"type":"object","properties":{"memory_id":{"type":"string"},"who":{"type":"array","items":{"type":"string"}},"what":{"type":"string"},"when":{"type":"string"},"where":{"type":"string"}},"required":["memory_id"]} }

    tool_schemas = [
        (photo_start_schema, lambda_arns.get('photo_service')),
        (photo_get_tags_schema, lambda_arns.get('photo_service')),
        (memory_remember_schema, lambda_arns.get('memory_service')),
        (memory_add_schema, lambda_arns.get('memory_service')),
    ]

    # Group schemas by Lambda function
    lambda_schemas = {}
    for schema, lambda_arn in tool_schemas:
        if lambda_arn:
            if lambda_arn not in lambda_schemas:
                lambda_schemas[lambda_arn] = []
            lambda_schemas[lambda_arn].append(schema)

    # List existing targets to avoid duplicates
    existing_targets = {}
    try:
        resp = client.list_gateway_targets(gatewayIdentifier=gateway_id)
        for t in resp.get('items', []):
            existing_targets[t['name']] = t
    except Exception as e:
        logger.info(f"list_gateway_targets error: {e}")

    # Create gateway targets with aggregated tool definitions per Lambda
    for lambda_arn, schemas in lambda_schemas.items():
        # Derive logical service name from lambda_arns mapping
        service_name = next((n for n, arn in lambda_arns.items() if arn == lambda_arn), None)
        if not service_name:
            logger.warning(f"Could not find service name for Lambda ARN: {lambda_arn}")
            continue
        
        # Replace underscores with hyphens to match API naming requirements
        target_name = service_name.replace('_', '-')
        
        if target_name in existing_targets:
            logger.info(f"Target {target_name} exists, skipping create (update not implemented).")
            continue
        try:
            inline_payload = _build_inline_payload(schemas)
            resp = client.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                description=f"MCP service for {service_name}",
                targetConfiguration={
                    'mcp': {
                        'lambda': {
                            'lambdaArn': lambda_arn,
                            # Per API spec: single toolSchema with inlinePayload list
                            'toolSchema': {
                                'inlinePayload': inline_payload
                            }
                        }
                    }
                },
                credentialProviderConfigurations=[
                    { 'credentialProviderType': 'GATEWAY_IAM_ROLE' }
                ]
            )
            logger.info(f"Created target {target_name} with {len(inline_payload)} tools")
        except ClientError as e:
            logger.error(f"Failed to create target {target_name}: {e}")

    # Retrieve gatewayUrl via list since describe_gateway not available in current client version
    gateway_url = None
    try:
        resp = client.list_gateways()
        for g in resp.get('items', []):
            if g.get('gatewayId') == gateway_id:
                gateway_url = g.get('gatewayUrl')
                break
    except Exception as e:
        logger.info(f"Unable to fetch gatewayUrl: {e}")
    return {"PhysicalResourceId": gateway_id, "Data":{"GatewayId": gateway_id, "GatewayUrl": gateway_url}}

def delete_gateway(event, context):
    props = event['ResourceProperties']
    region = props.get('Region')
    client = get_client(region)
    gateway_name = props.get('GatewayName')
    gaz = None
    try:
        resp = client.list_gateways()
        for g in resp.get('items', []):
            if g.get('name') == gateway_name:
                gaz = g
                break
    except Exception as e:
        logger.info(f"list_gateways failed: {e}")
    if not gaz:
        logger.info("No gateway to delete.")
        return {"PhysicalResourceId": gateway_name}
    gateway_id = gaz['gatewayId']
    try:
        resp = client.list_gateway_targets(gatewayIdentifier=gateway_id)
        for t in resp.get('items', []):
            try:
                client.delete_gateway_target(gatewayIdentifier=gateway_id, targetIdentifier=t['targetId'])
            except Exception as e:
                logger.info(f"Failed deleting target {t.get('name')}: {e}")
    except Exception as e:
        logger.info(f"list_gateway_targets failed: {e}")
    try:
        client.delete_gateway(gatewayIdentifier=gateway_id)
    except Exception as e:
        logger.info(f"delete_gateway failed: {e}")
    return {"PhysicalResourceId": gateway_id}

def lambda_handler(event, context):
    logger.info("Event: " + json.dumps(event))
    request_type = event.get('RequestType') or event.get('requestType') or 'Create'
    try:
        if request_type == 'Create' or request_type == 'Update':
            result = create_or_update_gateway(event, context)
            return result
        elif request_type == 'Delete':
            result = delete_gateway(event, context)
            return result
        else:
            logger.info("Unknown request type: " + str(request_type))
            return {"PhysicalResourceId": "unknown"}
    except Exception as e:
        logger.exception("Error in gateway manager")
        raise

def _build_inline_payload(schemas):
    """Return list of tool definition objects for inlinePayload (no byte encoding).
    The Bedrock AgentCore docs indicate inlinePayload accepts an array of tool definitions.
    We include outputSchema if present.
    """
    tools = []
    for s in schemas:
        if 'name' not in s or 'inputSchema' not in s:
            logger.warning(f"Skipping invalid tool schema missing required keys: {s.keys()}")
            continue
        tool_def = {
            'name': s.get('name'),
            'description': s.get('description'),
            'inputSchema': s.get('inputSchema')
        }
        # Optional fields
        if s.get('title'):
            tool_def['title'] = s.get('title')
        if s.get('outputSchema'):
            tool_def['outputSchema'] = s.get('outputSchema')
        tools.append(tool_def)
    return tools
