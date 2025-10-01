"""
Photo Memory Agent - Specialized Agent for Photo and Memory Management
Handles photo-related queries and memory operations using MCP tools via AgentCore Gateway.
"""

from strands import Agent
import logging
import os
import requests
import json
from typing import Dict, Any
from ..config.conversation_config import ConversationConfig, log_conversation_config
from ..config.config import create_bedrock_model

logger = logging.getLogger(__name__)


class PhotoMemoryAgent(Agent):
    """
    Specialized agent for photo and memory operations.
    Uses MCP tools exposed via AgentCore Gateway for photo management and memory storage.
    """

    def __init__(self, config=None):
        """
        Initialize the Photo Memory Agent.

        Args:
            config: AgentConfig instance for AWS profile and region settings
        """
        # Create properly configured Bedrock model
        bedrock_model = create_bedrock_model(config)

        # Create conversation manager for this agent
        conversation_manager = ConversationConfig.create_conversation_manager(
            "photomemory"
        )

        # Initialize Strands Agent with system prompt and tools
        system_prompt = self._get_system_prompt()
        super().__init__(
            model=bedrock_model,
            system_prompt=system_prompt,
            tools=self._get_tools(),
            conversation_manager=conversation_manager,
        )

        self.config = config
        
        # Initialize MCP Gateway connection details (but don't use them yet)
        self.gateway_url = os.environ.get('GATEWAY_URL')
        self.cognito_token_url = os.environ.get('COGNITO_TOKEN_URL')  
        self.oauth_client_id = os.environ.get('OAUTH_CLIENT_ID')
        self.oauth_client_secret = os.environ.get('OAUTH_CLIENT_SECRET')

    async def process_query(self, query: str) -> str:
        """
        Process a query for photo/memory operations.
        Since MCP Gateway is not available yet, return helpful placeholder responses.
        """
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['photo', 'picture', 'slideshow', 'album']):
            return """I'm your PhotoMemory Agent! I can help you with photo and memory management. 

For photos, I can:
- Start customized photo slideshows filtered by tags, dates, or people
- Get information about your photo tags and collections
- Organize and categorize your photos

For memories, I can:
- Store and organize your personal memories
- Help you recall past experiences
- Structure memory information with who, what, when, and where details

However, I need the AgentCore Gateway to be set up to access your actual photo and memory services. Once that's configured, I'll be able to perform these operations for you!

What kind of photo or memory task would you like help with?"""

        elif any(word in query_lower for word in ['memory', 'remember', 'recall']):
            return """I'd love to help you with your memories! I can store new memories and help you recall past ones.

I can help you:
- Record new memories in a structured way
- Parse freeform memory descriptions into organized data
- Search through your stored memories
- Recall specific memories by date, people, or events

To actually store and retrieve your memories, I need the AgentCore Gateway connection to be established. Once that's set up, I'll be able to access your memory database and provide these services.

What memory would you like to work with?"""

        else:
            return """Hello! I'm your PhotoMemory Agent, specialized in helping you manage photos and memories.

I can assist with:
🖼️ Photo Operations: Slideshows, organization, tagging, filtering
💭 Memory Management: Storing, organizing, and recalling personal memories

Currently, I'm running in demonstration mode since the AgentCore Gateway isn't set up yet. Once connected, I'll be able to access your actual photo and memory services.

How can I help you with your photos or memories today?"""        # Log configuration
        logger.info("PhotoMemoryAgent initialized with BedrockModel and MCP tools")
        log_conversation_config("PhotoMemoryAgent", conversation_manager)

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the Photo Memory Agent."""
        return """
You are a PhotoMemory Agent specialized in helping users manage their photos and memories. You have access to powerful tools for:

PHOTO OPERATIONS:
- Starting photo slideshows with filtering by tags, dates, people, locations
- Retrieving and analyzing photo tags and metadata
- Organizing photos by various criteria

MEMORY OPERATIONS:  
- Storing and retrieving personal memories
- Parsing freeform memory text into structured data (who, what, when, where)
- Adding new structured memories to the memory database
- Searching and recalling past memories

CAPABILITIES:
- photo_service.start_slideshow: Start a customized photo slideshow
- photo_service.get_tags: Get available photo tags and counts
- memory_service.remember: Parse and store freeform memory text
- memory_service.add_memory: Add structured memory data

CONVERSATION STYLE:
- Be warm, personal, and empathetic when dealing with memories
- Ask clarifying questions to better understand photo/memory requests
- Provide helpful suggestions for organizing photos and memories
- Remember context from previous interactions in the conversation

ALWAYS:
- Use the appropriate tools to fulfill user requests
- Provide clear explanations of what you're doing
- Handle errors gracefully and suggest alternatives
- Respect the personal nature of photos and memories

NEVER:
- Handle queries unrelated to photos or memories
- Make assumptions about personal information
- Expose sensitive memory details inappropriately
"""

    def _get_tools(self) -> list:
        """Get the tools available to this agent."""
        # For now, return empty list since AgentCore Gateway is not set up yet
        # TODO: Add MCP tools when Gateway is available
        return []

    def _get_token(self) -> str:
        """Get OAuth token from Cognito for MCP Gateway access."""
        if not all([self.cognito_token_url, self.oauth_client_id, self.oauth_client_secret]):
            raise RuntimeError('Missing Cognito token endpoint or client credentials in environment')
        
        resp = requests.post(
            self.cognito_token_url,
            data={'grant_type': 'client_credentials', 'client_id': self.oauth_client_id},
            auth=(self.oauth_client_id, self.oauth_client_secret)
        )
        resp.raise_for_status()
        return resp.json().get('access_token')

    def _call_mcp_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call an MCP tool via the AgentCore Gateway."""
        try:
            token = self._get_token()
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            body = {'name': tool_name, 'arguments': arguments}
            url = self.gateway_url.rstrip('/') + '/tools/call'
            
            logger.info(f"Calling MCP tool: {tool_name} with arguments: {arguments}")
            response = requests.post(url, headers=headers, data=json.dumps(body))
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"MCP tool {tool_name} returned: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {str(e)}")
            return {"error": str(e)}

    def _start_photo_slideshow(self, query: dict = None, settings: dict = None) -> str:
        """Start a photo slideshow using the MCP photo service."""
        try:
            arguments = {}
            if query:
                arguments['query'] = query
            if settings:
                arguments['settings'] = settings
                
            result = self._call_mcp_tool('photo_service.start_slideshow', arguments)
            
            if 'error' in result:
                return f"Error starting slideshow: {result['error']}"
            
            return f"Slideshow started successfully: {result.get('message', 'Started')}"
            
        except Exception as e:
            logger.error(f"Error in start_photo_slideshow: {str(e)}")
            return f"Error starting slideshow: {str(e)}"

    def _get_photo_tags(self) -> str:
        """Get available photo tags using the MCP photo service."""
        try:
            result = self._call_mcp_tool('photo_service.get_tags', {})
            
            if 'error' in result:
                return f"Error getting photo tags: {result['error']}"
            
            tags = result.get('tags', [])
            if not tags:
                return "No photo tags found."
            
            tag_summary = "Available photo tags:\n"
            for tag_info in tags:
                tag_name = tag_info.get('tag', 'Unknown')
                count = tag_info.get('count', 0)
                tag_summary += f"- {tag_name}: {count} photos\n"
            
            return tag_summary
            
        except Exception as e:
            logger.error(f"Error in get_photo_tags: {str(e)}")
            return f"Error getting photo tags: {str(e)}"

    def _remember_memory(self, text: str) -> str:
        """Parse and store a freeform memory using the MCP memory service."""
        try:
            arguments = {'text': text}
            result = self._call_mcp_tool('memory_service.remember', arguments)
            
            if 'error' in result:
                return f"Error storing memory: {result['error']}"
            
            memory_id = result.get('memory_id', 'Unknown')
            who = result.get('who', [])
            what = result.get('what', '')
            when = result.get('when', '')
            where = result.get('where', '')
            
            response = f"Memory stored successfully (ID: {memory_id})\n"
            response += f"Who: {', '.join(who) if who else 'Not specified'}\n"
            response += f"What: {what}\n"
            response += f"When: {when}\n"
            response += f"Where: {where}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error in remember_memory: {str(e)}")
            return f"Error storing memory: {str(e)}"

    def _add_structured_memory(self, who: list = None, what: str = "", when: str = "", where: str = "") -> str:
        """Add a structured memory using the MCP memory service."""
        try:
            arguments = {
                'who': who or [],
                'what': what,
                'when': when,
                'where': where
            }
            result = self._call_mcp_tool('memory_service.add_memory', arguments)
            
            if 'error' in result:
                return f"Error adding memory: {result['error']}"
            
            memory_id = result.get('memory_id', 'Unknown')
            return f"Structured memory added successfully (ID: {memory_id})"
            
        except Exception as e:
            logger.error(f"Error in add_structured_memory: {str(e)}")
            return f"Error adding memory: {str(e)}"

    async def handle_query(self, query: str) -> str:
        """
        Handle a photo/memory related query.

        Args:
            query: User query about photos or memories

        Returns:
            Response from processing the query
        """
        logger.info(f"PhotoMemoryAgent handling query: {query}")
        
        try:
            # Check if MCP Gateway is configured
            if not self.gateway_url:
                logger.warning("MCP Gateway not configured, using placeholder response")
                return "PhotoMemory Agent is ready, but MCP Gateway is not configured. Please set GATEWAY_URL and related environment variables."
            
            # Use the Strands Agent's call method to handle the query
            response = self(query)
            logger.info("PhotoMemoryAgent query processed successfully")
            return response
            
        except Exception as e:
            logger.error(f"Error in PhotoMemoryAgent: {str(e)}")
            return f"Error processing photo/memory query: {str(e)}"