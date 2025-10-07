#!/usr/bin/env python3
"""
Script to manually clean up existing gateways before deployment
"""
import boto3
import json
from botocore.exceptions import ClientError

def cleanup_gateways():
    region = 'us-east-1'
    gateway_name = 'photoagent-gateway'
    
    client = boto3.client('bedrock-agentcore-control', region_name=region)
    
    print(f"Looking for gateways named '{gateway_name}' in region {region}...")
    
    try:
        # List all gateways
        resp = client.list_gateways()
        gateways = resp.get('items', [])
        
        print(f"Found {len(gateways)} total gateways:")
        for g in gateways:
            print(f"  - {g.get('name')} (ID: {g.get('gatewayId')}, Status: {g.get('gatewayStatus')})")
        
        # Find and delete the specific gateway
        target_gateway = None
        for g in gateways:
            if g.get('name') == gateway_name:
                target_gateway = g
                break
        
        if target_gateway:
            gateway_id = target_gateway['gatewayId']
            print(f"\nFound target gateway: {gateway_name} (ID: {gateway_id})")
            
            # First delete all targets - retry multiple times to ensure all are gone
            max_retries = 3
            for retry in range(max_retries):
                print(f"\n--- Attempt {retry + 1} to clean up targets ---")
                try:
                    targets_resp = client.list_gateway_targets(gatewayIdentifier=gateway_id)
                    targets = targets_resp.get('items', [])
                    
                    if not targets:
                        print("No targets found - ready to delete gateway")
                        break
                        
                    print(f"Found {len(targets)} targets to delete:")
                    
                    for target in targets:
                        target_id = target['targetId']
                        target_name = target.get('name', 'unknown')
                        print(f"  Deleting target: {target_name} (ID: {target_id})")
                        try:
                            client.delete_gateway_target(
                                gatewayIdentifier=gateway_id,
                                targetId=target_id
                            )
                            print(f"    ✓ Deleted target {target_name}")
                        except ClientError as e:
                            print(f"    ✗ Failed to delete target {target_name}: {e}")
                
                except ClientError as e:
                    print(f"Failed to list targets: {e}")
                    if retry == max_retries - 1:
                        print("Max retries reached for target cleanup")
            
            # Now delete the gateway
            print(f"\nDeleting gateway: {gateway_name}")
            try:
                client.delete_gateway(gatewayIdentifier=gateway_id)
                print(f"✓ Successfully deleted gateway {gateway_name}")
            except ClientError as e:
                print(f"✗ Failed to delete gateway: {e}")
                # If it still fails, list remaining targets for debugging
                try:
                    targets_resp = client.list_gateway_targets(gatewayIdentifier=gateway_id)
                    remaining_targets = targets_resp.get('items', [])
                    if remaining_targets:
                        print(f"Remaining targets preventing deletion:")
                        for t in remaining_targets:
                            print(f"  - {t.get('name', 'unknown')} (ID: {t['targetId']})")
                except:
                    pass
        else:
            print(f"\nNo gateway named '{gateway_name}' found. Nothing to clean up.")
    
    except ClientError as e:
        print(f"Error listing gateways: {e}")
        print("Make sure you have the correct AWS credentials and permissions.")

if __name__ == "__main__":
    cleanup_gateways()