"""
Supervisor Agent - Pure Router
Routes user queries to appropriate specialized agents without any tools or reasoning.
"""

from strands import Agent
from typing import Dict, Any
from ..config.conversation_config import ConversationConfig, log_conversation_config
from ..config.config import create_bedrock_model
import logging

logger = logging.getLogger(__name__)


class SupervisorAgent(Agent):
    """
    Supervisor Agent that acts as a pure router.
    No tools, no reasoning - just routing based on query type.
    """

    def __init__(self, specialized_agents: Dict[str, Agent], config=None):
        """
        Initialize supervisor with references to specialized agents.

        Args:
            specialized_agents: Dictionary mapping agent names to agent instances
            config: AgentConfig instance for AWS profile and region settings
        """
        # Create properly configured Bedrock model with specified profile
        bedrock_model = create_bedrock_model(config)

        # Create conversation manager for supervisor (smaller window since it just routes)
        conversation_manager = ConversationConfig.create_conversation_manager(
            "supervisor"
        )

        # Initialize Strands Agent with system prompt but no tools
        system_prompt = self._get_routing_instructions()
        super().__init__(
            model=bedrock_model,
            system_prompt=system_prompt,
            tools=[],  # No tools for pure router
            conversation_manager=conversation_manager,
        )

        self.specialized_agents = specialized_agents

        # Log configuration
        logger.info(
            "SupervisorAgent initialized with BedrockModel (configured profile, us-east-1, Claude 3 Haiku)"
        )
        log_conversation_config("SupervisorAgent", conversation_manager)
        logger.info(
            f"Supervisor initialized with agents: {list(specialized_agents.keys())} and conversation management"
        )

    def _get_routing_instructions(self) -> str:
        """Get the routing instructions for the supervisor."""
        return """
You are a Supervisor Agent that acts as a pure router for photo and memory-related queries. Your job is to:

1. First, validate that the query is photo or memory-related
2. If not related to photos/memories, politely redirect to those topics
3. Route the query to the appropriate agent
4. Return the agent's response

QUERY VALIDATION:
- ONLY handle queries about photos, memories, slideshows, or personal recollections
- Accept queries about: photo management, slideshows, viewing photos, organizing photos, storing memories, recalling events, etc.
- Reject queries about: non-photo/memory topics
- For non-photo/memory queries, respond: "I'm specialized in photo and memory management. Please ask about viewing photos, creating slideshows, or storing memories."

ROUTING RULES (for valid photo/memory queries):
- ALL photo and memory related queries → PhotoMemoryAgent

CONVERSATION CONTEXT:
- Remember previous photo/memory interactions
- Consider conversation flow when handling follow-up questions
- Route follow-up questions to PhotoMemoryAgent when contextually relevant

DO NOT:
- Use any tools yourself
- Perform reasoning about photo operations
- Make direct API calls
- Provide technical solutions outside photo/memory domain
- Handle non-photo/memory queries

ALWAYS:
- Validate query is photo/memory-related first
- Route to PhotoMemoryAgent for valid queries
- Pass the original user query unchanged to the agent
- Return the specialized agent's response
- Consider conversation history for routing decisions
"""

    async def route_query(self, query: str) -> str:
        """
        Route a query to the appropriate specialized agent.

        Args:
            query: User query to route

        Returns:
            Response from the specialized agent
        """
        logger.info(f"Routing query: {query}")

        # Determine which agent to route to
        agent_name = self._determine_agent(query)

        if agent_name not in self.specialized_agents:
            logger.error(f"Agent {agent_name} not found in specialized agents")
            return f"Error: Unable to route query - {agent_name} not available"

        # Route to specialized agent
        specialized_agent = self.specialized_agents[agent_name]
        logger.info(f"Routing to {agent_name}")

        try:
            # Use the Strands Agent's direct call method
            response = specialized_agent(query)
            logger.info(f"Received response from {agent_name}")
            return response

        except Exception as e:
            logger.error(f"Error from {agent_name}: {str(e)}")
            return f"Error: {agent_name} encountered an issue: {str(e)}"

    def _determine_agent(self, query: str) -> str:
        """
        Determine which agent should handle the query based on keywords.

        Args:
            query: User query

        Returns:
            Name of the agent to route to
        """
        query_lower = query.lower()

        # Photo and memory keywords
        photo_memory_keywords = [
            "photo", "photos", "picture", "pictures", "image", "images",
            "slideshow", "gallery", "album", "memory", "memories", 
            "remember", "recall", "event", "moment", "tag", "tags",
            "when", "where", "who", "what happened", "show me",
            "view", "display", "organize", "search", "find"
        ]

        # Check for photo/memory related content
        if any(keyword in query_lower for keyword in photo_memory_keywords):
            return "PhotoMemoryAgent"

        # Default to PhotoMemoryAgent for all queries (since this is a photo/memory system)
        return "PhotoMemoryAgent"
