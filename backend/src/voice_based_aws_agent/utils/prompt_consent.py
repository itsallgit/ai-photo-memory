"""
Prompt-based Consent System for some operations.
"""

# Define dangerous operations that require consent
DANGEROUS_OPERATIONS = {
    'photomemory': [
        'start-slideshow'
    ]
}

def get_consent_instructions() -> str:
    """
    Get prompt instructions for handling dangerous operations.
    This is added to agent system prompts to enable consent checking.
    """
    return f"""
IMPORTANT SAFETY PROTOCOL FOR SOME OPERATIONS:

Before executing ANY of these dangerous operations, you MUST ask for explicit user consent:

DANGEROUS PHOTO MEMORY OPERATIONS (require consent):
- start-slideshow (shows photos on the user's home gallery device)
- add-memory (stores a new memory entry)

CONSENT PROTOCOL:
1. If user requests a dangerous operation, DO NOT use a tool immediately
2. First explain what the operation will do and its potential impact
3. Ask for explicit consent: "Do you want me to proceed? Please say 'yes' to continue or 'no' to cancel."
4. Wait for user response
5. Only use a tool if user explicitly approves (says "yes", "proceed", "continue", etc.)
6. If user declines or seems uncertain, do not execute the operation

SAFE OPERATIONS (no consent needed):
- get-tags
- remember

EXAMPLE CONSENT FLOW:
User: "Show me photos from my last trip"
Agent: "I can start a slideshow for you of photos from your last trip. This will update your home gallery device. Do you want me to proceed? Please say 'yes' to continue or 'no' to cancel."
User: "yes"
Agent: "Cool beans! Starting slideshow noe..." [then uses tool to start slideshow]

EXAMPLE DENIAL:
User: "I want you to remember that"
Agent: "I can add a new memory if you like. Do you want me to proceed? Please say 'yes' to continue or 'no' to cancel."
User: "no"
Agent: "No worries. Let me know any time you want to add a memory."

Remember: ALWAYS ask for consent before dangerous operations. NEVER assume the user wants to proceed with dangerous actions.
"""

def is_dangerous_operation(service: str, operation: str) -> bool:
    """
    Check if an operation is dangerous and requires consent.
    
    Args:
        service: specialised agent (e.g., 'photomemory')
        operation: agent tool (e.g., 'start-slideshow')
        
    Returns:
        True if operation requires consent, False otherwise
    """
    service_lower = service.lower()
    operation_lower = operation.lower()
    
    dangerous_ops = DANGEROUS_OPERATIONS.get(service_lower, [])
    return operation_lower in dangerous_ops