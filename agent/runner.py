"""
The agent loop.

This is the Python equivalent of n8n's AI Agent node. It:
  1. Builds the message list (conversation history + current user message)
  2. Calls Claude with the system prompt and tool schemas
  3. If Claude wants to use a tool → executes it and feeds results back
  4. Repeats until Claude gives a final text response
  5. Returns the final response string
"""

import logging
from pathlib import Path

import anthropic
import config
from agent.tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None

SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system_prompt.txt"


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _load_system_prompt(recent_conversation: str) -> str:
    """Load the system prompt and inject the recent conversation context."""
    base_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return f"Recent Conversation:\n{recent_conversation}\n\n{base_prompt}"


def run_agent(user_message: str, recent_conversation: str) -> str:
    """
    Run the full agent loop for a single user turn.

    Args:
        user_message       : The raw text sent by the Telegram user
        recent_conversation: Formatted string of recent chat history

    Returns:
        The agent's final text response to send back to the user
    """
    client = _get_client()
    system_prompt = _load_system_prompt(recent_conversation)

    # Start with just the user's current message
    messages = [{"role": "user", "content": user_message}]

    max_iterations = 10  # Safety limit on the tool-use loop
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Agent iteration {iteration}")

        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # --- Final answer: Claude is done ---
        if response.stop_reason == "end_turn":
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return " ".join(text_blocks).strip()

        # --- Tool use: Claude wants to call one or more tools ---
        if response.stop_reason == "tool_use":
            # Append Claude's response (which contains tool_use blocks) to history
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool Claude requested and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result_content = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    })

            # Feed the tool results back as a user turn
            messages.append({"role": "user", "content": tool_results})
            continue

        # Unexpected stop reason
        logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
        break

    return "I'm sorry, I had trouble processing that. Please try again."
