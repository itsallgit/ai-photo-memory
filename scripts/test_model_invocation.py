#!/usr/bin/env python3
"""
Helper script to test AWS Bedrock model invocation.
Returns exit code 0 if successful, 1 if failed.
"""

import sys
import json
import boto3
import argparse
from botocore.exceptions import ClientError, NoCredentialsError


def test_model_invocation(model_id, profile_name, region, verbose=False):
    """
    Test if a Bedrock model can be invoked successfully.
    
    Args:
        model_id (str): The Bedrock model ID to test
        profile_name (str): AWS profile name
        region (str): AWS region
        verbose (bool): Whether to print detailed output
    
    Returns:
        bool: True if model can be invoked, False otherwise
    """
    try:
        # Create boto3 session with profile
        session = boto3.Session(profile_name=profile_name)
        client = session.client('bedrock-runtime', region_name=region)
        
        if verbose:
            print(f"Testing model: {model_id}")
            print(f"Profile: {profile_name}")
            print(f"Region: {region}")
        
        # Prepare test request based on model type
        if 'claude' in model_id.lower():
            # Claude models use messages format with anthropic_version
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5
            }
        elif 'nova-sonic' in model_id.lower():
            # Nova Sonic is a speech model - we'll test basic invoke capability
            # Note: This might still fail due to audio input requirements
            body = {
                "inputText": "test"
            }
        elif 'nova' in model_id.lower():
            # Other Nova models (text models)
            body = {
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5
            }
        elif 'titan' in model_id.lower():
            # Amazon Titan models
            body = {
                "inputText": "Say OK",
                "textGenerationConfig": {
                    "maxTokenCount": 5,
                    "temperature": 0.7,
                    "topP": 0.9
                }
            }
        else:
            # Generic test for other models
            body = {
                "prompt": "Say OK",
                "max_tokens": 5
            }
        
        # Attempt to invoke the model
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType='application/json',
            accept='application/json'
        )
        
        # If we get here without exception, the model is accessible
        if verbose:
            try:
                result = json.loads(response['body'].read())
                print(f"✅ Model invocation successful!")
                
                # Try to extract response text based on model type
                if 'claude' in model_id.lower() and 'content' in result:
                    print(f"Response: {result['content'][0]['text']}")
                elif 'completion' in result:
                    print(f"Response: {result['completion']}")
                elif 'results' in result:
                    print(f"Response: {result['results'][0]['outputText']}")
                else:
                    print(f"Raw response keys: {list(result.keys())}")
            except Exception as parse_error:
                print(f"✅ Model invocation successful (response parsing failed: {parse_error})")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if verbose:
            print(f"❌ Model invocation failed: {error_code}")
            print(f"Error message: {error_message}")
            
            if error_code == 'AccessDeniedException':
                print("💡 This usually means you need to request model access in the Bedrock console")
            elif error_code == 'ValidationException':
                print("💡 This might be due to incorrect request format for this model type")
        
        return False
        
    except NoCredentialsError:
        if verbose:
            print(f"❌ No AWS credentials found for profile: {profile_name}")
        return False
        
    except Exception as e:
        if verbose:
            print(f"❌ Unexpected error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Test AWS Bedrock model invocation')
    parser.add_argument('model_id', help='Bedrock model ID to test')
    parser.add_argument('--profile', required=True, help='AWS profile name')
    parser.add_argument('--region', default='us-east-1', help='AWS region (default: us-east-1)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Test the model
    success = test_model_invocation(
        model_id=args.model_id,
        profile_name=args.profile,
        region=args.region,
        verbose=args.verbose
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()