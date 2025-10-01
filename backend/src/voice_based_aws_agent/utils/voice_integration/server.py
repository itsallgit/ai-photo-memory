#!/usr/bin/env python3
"""
Simple WebSocket server
"""

import asyncio
import websockets
import json
import logging
import warnings
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from .s2s_session_manager import S2sSessionManager
from src.voice_based_aws_agent.utils.aws_auth import get_aws_session
from src.voice_based_aws_agent.config.config import AgentConfig

# Configure logging - reduce WebSocket verbosity while keeping agent logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebSocketServer")

# Set specific log levels for different components
websocket_logger = logging.getLogger("WebSocketServer")
websocket_logger.setLevel(logging.WARNING)  # Reduce WebSocket noise

# Keep agent logs visible
agent_logger = logging.getLogger("AgentOrchestrator")
agent_logger.setLevel(logging.INFO)

# Keep tool logs visible
tool_logger = logging.getLogger("SupervisorTool")
tool_logger.setLevel(logging.INFO)

# Suppress warnings
warnings.filterwarnings("ignore")

async def websocket_handler(websocket, path, config):
    """Handle WebSocket connections - simplified version"""
    stream_manager = None
    forward_task = None
    
    logger.info(f"New WebSocket connection from {websocket.remote_address}")
    
    try:
        async for message in websocket:
            logger.debug(f"Received WebSocket message: {message[:100]}...")  # Log first 100 chars at debug level
            try:
                data = json.loads(message)
                logger.debug(f"Parsed JSON data keys: {data.keys() if data else 'None'}")
                if 'body' in data:
                    data = json.loads(data["body"])
                    logger.debug(f"Parsed body data keys: {data.keys() if data else 'None'}")
                
                if 'event' in data:
                    event_type = list(data['event'].keys())[0]
                    logger.debug(f"Event type received: {event_type}")
                    
                    # Initialize stream manager only once per WebSocket connection
                    if stream_manager is None:
                        logger.info("Initializing simple stream manager")
                        try:
                            stream_manager = S2sSessionManager(
                                model_id='amazon.nova-sonic-v1:0',
                                region='us-east-1',
                                config=config
                            )
                            
                            # Initialize the Bedrock stream
                            logger.info("Initializing Bedrock stream...")
                            await stream_manager.initialize_stream()
                            logger.info("Bedrock stream initialized successfully")
                            
                            # Start a task to forward responses from Bedrock to the WebSocket
                            logger.debug("Starting response forwarding task...")
                            forward_task = asyncio.create_task(forward_responses(websocket, stream_manager))
                            logger.info("Stream manager fully initialized")
                        except Exception as e:
                            logger.error(f"Failed to initialize stream manager: {e}")
                            logger.error(f"Exception type: {type(e).__name__}")
                            import traceback
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            # Continue without stream manager - will use fallback
                            stream_manager = None
                    
                    # Store prompt name and content names if provided
                    if event_type == 'promptStart':
                        if stream_manager:
                            stream_manager.prompt_name = data['event']['promptStart']['promptName']
                    elif event_type == 'contentStart' and data['event']['contentStart'].get('type') == 'AUDIO':
                        if stream_manager:
                            stream_manager.audio_content_name = data['event']['contentStart']['contentName']
                    
                    # Handle audio input separately
                    if event_type == 'audioInput':
                        logger.debug(f"Processing audioInput event")
                        if stream_manager:
                            # Extract audio data
                            prompt_name = data['event']['audioInput']['promptName']
                            content_name = data['event']['audioInput']['contentName']
                            audio_base64 = data['event']['audioInput']['content']
                            
                            logger.debug(f"Audio data: prompt={prompt_name}, content={content_name}, data_length={len(audio_base64) if audio_base64 else 0}")
                            # Add to the audio queue
                            stream_manager.add_audio_chunk(prompt_name, content_name, audio_base64)
                        else:
                            logger.warning("Received audioInput but stream_manager is None")
                    else:
                        logger.debug(f"Sending non-audio event to Bedrock: {event_type}")
                        if stream_manager:
                            # Send other events directly to Bedrock
                            await stream_manager.send_raw_event(data)
                        else:
                            logger.warning(f"Cannot send {event_type} event - stream_manager is None")
                else:
                    logger.debug(f"No 'event' key found in data: {data}")
                    continue
                        
            except json.JSONDecodeError:
                logger.error("Invalid JSON received from WebSocket")
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                    
    except websockets.exceptions.ConnectionClosed:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
    finally:
        # Clean up
        logger.info("Cleaning up WebSocket connection")
        if stream_manager:
            stream_manager.close()
        if forward_task and not forward_task.done():
            forward_task.cancel()
        logger.info("WebSocket connection cleanup complete")

async def forward_responses(websocket, stream_manager):
    """Forward responses from Bedrock to the WebSocket - simplified version"""
    try:
        while stream_manager.is_active:
            # Get next response from the output queue
            response = await stream_manager.output_queue.get()
            
            # Send to WebSocket
            try:
                event = json.dumps(response)
                await websocket.send(event)
            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket connection closed during response forwarding")
                break
            except Exception as send_error:
                logger.error(f"Error sending response to WebSocket: {send_error}")
                break
                
    except asyncio.CancelledError:
        logger.info("Response forwarding task cancelled")
    except Exception as e:
        logger.error(f"Error forwarding responses: {e}")
    finally:
        logger.info("Response forwarding stopped")

async def main(host, port, config):
    """Main function to run the WebSocket server"""
    try:
        # Start WebSocket server
        async with websockets.serve(
            lambda ws, path: websocket_handler(ws, path, config),
            host,
            port
        ):
            logger.info(f"Simple WebSocket server started at {host}:{port}")
            
            # Keep the server running forever
            await asyncio.Future()
    except Exception as e:
        logger.error(f"Failed to start WebSocket server: {e}")

async def run_server(profile_name=None, region=None, host="localhost", port=80):
    """Run the simple WebSocket server"""
    # Create agent configuration
    config = AgentConfig(
        profile_name=profile_name,
        region=region or "us-east-1"
    )
    
    # Ensure AWS credentials are available
    session = get_aws_session(config.profile_name)
    if not session:
        logger.error("Failed to get AWS session. Check your credentials.")
        return
    
    try:
        await main(host, port, config)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Simple Nova S2S WebSocket Server")
    parser.add_argument("--profile", help="AWS profile name")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=80, help="Port to bind to")
    
    args = parser.parse_args()
    
    asyncio.run(run_server(
        profile_name=args.profile,
        region=args.region,
        host=args.host,
        port=args.port
    ))
