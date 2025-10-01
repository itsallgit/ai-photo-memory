import asyncio
import json
import base64
import warnings
import uuid
import os
import logging
from .s2s_events import S2sEvent
import time
from aws_sdk_bedrock_runtime.client import BedrockRuntimeClient, InvokeModelWithBidirectionalStreamOperationInput
from aws_sdk_bedrock_runtime.models import InvokeModelWithBidirectionalStreamInputChunk, BidirectionalInputPayloadPart
from aws_sdk_bedrock_runtime.config import Config, HTTPAuthSchemeResolver, SigV4AuthScheme
from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver
from .supervisor_agent_integration import SupervisorAgentIntegration

# Suppress warnings
warnings.filterwarnings("ignore")

# Set up logging
logger = logging.getLogger("S2sSessionManager")

DEBUG = False

def debug_print(message):
    """Print only if debug mode is enabled"""
    if DEBUG:
        print(f"[DEBUG S2S] {message}")
    logger.debug(message)


class S2sSessionManager:
    """Simple S2S Session Manager """
    
    def __init__(self, model_id='amazon.nova-sonic-v1:0', region='us-east-1', config=None):
        """Initialize the stream manager."""
        self.model_id = model_id
        self.region = region
        
        # Audio and output queues
        self.audio_input_queue = asyncio.Queue()
        self.output_queue = asyncio.Queue()
        
        self.response_task = None
        self.stream = None
        self.is_active = False
        self.bedrock_client = None
        
        # Session information
        self.prompt_name = None  # Will be set from frontend
        self.content_name = None  # Will be set from frontend
        self.audio_content_name = None  # Will be set from frontend
        self.toolUseContent = ""
        self.toolUseId = ""
        self.toolName = ""
        
        # Initialize the Supervisor Agent integration
        self.supervisor_agent = SupervisorAgentIntegration(config)

    def _initialize_client(self):
        """Initialize the Bedrock client."""
        debug_print("Initializing Bedrock client...")
        
        # Use environment credentials resolver which will pick up AWS_PROFILE
        aws_profile = os.environ.get('AWS_PROFILE', 'default')
        aws_region = os.environ.get('AWS_DEFAULT_REGION', self.region)
        debug_print(f"Using AWS profile: {aws_profile}")
        debug_print(f"Using AWS region: {aws_region}")
        debug_print(f"Endpoint: https://bedrock-runtime.{self.region}.amazonaws.com")
        
        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            auth_scheme_resolver=HTTPAuthSchemeResolver(),
            auth_schemes={"aws.auth#sigv4": SigV4AuthScheme(service="bedrock")}
        )
        self.bedrock_client = BedrockRuntimeClient(config=config)
        debug_print("Bedrock client initialized successfully")

    async def initialize_stream(self):
        """Initialize the bidirectional stream with Bedrock."""
        debug_print("Starting stream initialization...")
        try:
            if not self.bedrock_client:
                debug_print("Bedrock client not initialized, initializing now...")
                self._initialize_client()
            debug_print("Bedrock client ready")
        except Exception as ex:
            self.is_active = False
            debug_print(f"Failed to initialize Bedrock client: {str(ex)}")
            print(f"Failed to initialize Bedrock client: {str(ex)}")
            raise

        try:
            debug_print(f"Creating bidirectional stream with model: {self.model_id}")
            # Initialize the stream with a timeout
            start_time = time.time()
            self.stream = await asyncio.wait_for(
                self.bedrock_client.invoke_model_with_bidirectional_stream(
                    InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_id)
                ), 
                timeout=30.0  # 30 second timeout
            )
            end_time = time.time()
            debug_print(f"Bedrock stream created successfully in {end_time - start_time:.2f} seconds")
            self.is_active = True
            
            debug_print("Starting response processor task...")
            # Start listening for responses
            self.response_task = asyncio.create_task(self._process_responses())

            debug_print("Starting audio input processor task...")
            # Start processing audio input
            asyncio.create_task(self._process_audio_input())
            
            # Wait a bit to ensure everything is set up
            debug_print("Waiting for initialization to complete...")
            await asyncio.sleep(0.1)
            
            debug_print("Stream initialized successfully")
            return self
        except asyncio.TimeoutError:
            self.is_active = False
            debug_print("Timeout: Bedrock stream initialization took longer than 30 seconds")
            print("Timeout: Bedrock stream initialization took longer than 30 seconds")
            raise
        except Exception as e:
            self.is_active = False
            debug_print(f"Failed to initialize stream: {str(e)}")
            debug_print(f"Exception type: {type(e).__name__}")
            print(f"Failed to initialize stream: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            raise
    
    async def send_raw_event(self, event_data):
        """Send a raw event to the Bedrock stream."""
        try:
            if not self.stream or not self.is_active:
                debug_print("Stream not initialized or closed")
                return
            
            event_json = json.dumps(event_data)
            event = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=event_json.encode('utf-8'))
            )
            await self.stream.input_stream.send(event)

            # Close session
            if "sessionEnd" in event_data["event"]:
                self.close()
            
        except Exception as e:
            debug_print(f"Error sending event: {str(e)}")
    
    async def _process_audio_input(self):
        """Process audio input from the queue and send to Bedrock."""
        debug_print("Starting audio input processing loop")
        while self.is_active:
            try:
                debug_print("Waiting for audio data from queue...")
                # Get audio data from the queue
                data = await self.audio_input_queue.get()
                debug_print(f"Got audio data from queue: {data.keys() if data else 'None'}")
                
                # Extract data from the queue item
                prompt_name = data.get('prompt_name')
                content_name = data.get('content_name')
                audio_bytes = data.get('audio_bytes')
                
                if not audio_bytes or not prompt_name or not content_name:
                    debug_print("Missing required audio data properties")
                    continue

                debug_print(f"Processing audio: prompt={prompt_name}, content={content_name}")
                # Create the audio input event
                audio_event = S2sEvent.audio_input(prompt_name, content_name, audio_bytes.decode('utf-8') if isinstance(audio_bytes, bytes) else audio_bytes)
                
                # Send the event
                debug_print("Sending audio event to Bedrock...")
                await self.send_raw_event(audio_event)
                debug_print("Audio event sent successfully")
                
            except asyncio.CancelledError:
                debug_print("Audio processing cancelled")
                break
            except Exception as e:
                debug_print(f"Error processing audio: {e}")
    
    def add_audio_chunk(self, prompt_name, content_name, audio_data):
        """Add an audio chunk to the queue."""
        debug_print(f"Adding audio chunk: prompt={prompt_name}, content={content_name}, data_length={len(audio_data) if audio_data else 0}")
        # The audio_data is already a base64 string from the frontend
        self.audio_input_queue.put_nowait({
            'prompt_name': prompt_name,
            'content_name': content_name,
            'audio_bytes': audio_data
        })
        debug_print(f"Audio queue size now: {self.audio_input_queue.qsize()}")
    
    async def _process_responses(self):
        """Process incoming responses from Bedrock."""
        while self.is_active:
            try:            
                output = await self.stream.await_output()
                result = await output[1].receive()
                
                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode('utf-8')
                    
                    json_data = json.loads(response_data)
                    json_data["timestamp"] = int(time.time() * 1000)  # Milliseconds since epoch
                    
                    event_name = None
                    if 'event' in json_data:
                        event_name = list(json_data["event"].keys())[0]
                        
                        # Handle tool use detection
                        if event_name == 'toolUse':
                            self.toolUseContent = json_data['event']['toolUse']
                            self.toolName = json_data['event']['toolUse']['toolName']
                            self.toolUseId = json_data['event']['toolUse']['toolUseId']
                            debug_print(f"Tool use detected: {self.toolName}, ID: {self.toolUseId}")

                        # Process tool use when content ends
                        elif event_name == 'contentEnd' and json_data['event'][event_name].get('type') == 'TOOL':
                            prompt_name = json_data['event']['contentEnd'].get("promptName")
                            debug_print("Processing tool use and sending result")
                            toolResult = await self.processToolUse(self.toolName, self.toolUseContent)
                                
                            # Send tool start event
                            toolContent = str(uuid.uuid4())
                            tool_start_event = S2sEvent.content_start_tool(prompt_name, toolContent, self.toolUseId)
                            await self.send_raw_event(tool_start_event)
                            
                            # Send tool result event
                            if isinstance(toolResult, dict):
                                content_json_string = json.dumps(toolResult)
                            else:
                                content_json_string = toolResult

                            tool_result_event = S2sEvent.text_input_tool(prompt_name, toolContent, content_json_string)
                            print("Tool result", tool_result_event)
                            await self.send_raw_event(tool_result_event)

                            # Send tool content end event
                            tool_content_end_event = S2sEvent.content_end(prompt_name, toolContent)
                            await self.send_raw_event(tool_content_end_event)
                    
                    # Put the response in the output queue for forwarding to the frontend
                    await self.output_queue.put(json_data)

            except json.JSONDecodeError as ex:
                print(ex)
                await self.output_queue.put({"raw_data": response_data})
            except StopAsyncIteration as ex:
                # Stream has ended
                print(ex)
                break
            except Exception as e:
                # Handle ValidationException properly
                if "ValidationException" in str(e):
                    error_message = str(e)
                    print(f"Validation error: {error_message}")
                else:
                    print(f"Error receiving response: {e}")
                break

        self.is_active = False
        self.close()

    async def processToolUse(self, toolName, toolUseContent):
        """Process tool use with Supervisor Agent - simplified version"""
        print(f"Tool Use Content: {toolUseContent}")

        toolName = toolName.lower()
        content, result = None, None
        try:
            if toolUseContent.get("content"):
                content = toolUseContent.get("content")
                print(f"Extracted query: {content}")
            
            # Process with the Supervisor Agent (our main tool)
            if toolName == "supervisoragent":
                # Parse the content if it's JSON
                if isinstance(content, str):
                    try:
                        content_obj = json.loads(content)
                        if "query" in content_obj:
                            query = content_obj["query"]
                        else:
                            query = content
                    except:
                        query = content
                else:
                    query = str(content)
                
                # Get the result from the supervisor agent
                result = await self.supervisor_agent.query(query)
                
                # Ensure the result is a string and limit length
                if not isinstance(result, str):
                    if hasattr(result, 'content'):
                        result = result.content
                    else:
                        result = str(result)
                
                # Limit result length for voice
                if len(result) > 800:
                    result = result[:800] + "... (truncated for voice)"
                
                print(f"Supervisor agent result: {result[:100]}...")

            if not result:
                result = "I couldn't process that request. Please try asking about photos and memories."

            return {"result": result}
        except Exception as ex:
            print(f"Error in processToolUse: {ex}")
            return {"result": f"Sorry, I encountered an error: {str(ex)}"}
    
    def close(self):
        """Close the stream properly."""
        if not self.is_active:
            return
            
        self.is_active = False
        
        if self.stream:
            # Don't await here to avoid blocking
            asyncio.create_task(self.stream.input_stream.close())
        
        if self.response_task and not self.response_task.done():
            self.response_task.cancel()
