"""
Inter-Agent Message Bus (Phase 41)
Provides direct messaging, query-response handoffs, task delegation, and broadcast channels.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import uuid


class InterAgentMessageBus:
    """In-memory communication coordinator for collaborative agent teams."""

    def __init__(self):
        self._messages: List[Dict[str, Any]] = []

    def send_message(
        self,
        sender_agent: str,
        recipient_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches an inter-agent message."""
        msg = {
            "id": str(uuid.uuid4()),
            "task_id": task_id,
            "sender_agent": sender_agent,
            "recipient_agent": recipient_agent,
            "message_type": message_type,  # QUERY, RESPONSE, DELEGATION, DISPUTE
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._messages.append(msg)
        return msg

    def delegate_task(
        self,
        supervisor_agent: str,
        subordinate_agent: str,
        subtask_goal: str,
        input_data: Dict[str, Any],
        parent_task_id: str,
    ) -> Dict[str, Any]:
        """Formal task delegation from a planning/supervisor agent to a specialized agent."""
        return self.send_message(
            sender_agent=supervisor_agent,
            recipient_agent=subordinate_agent,
            message_type="DELEGATION",
            payload={"subtask_goal": subtask_goal, "input_data": input_data},
            task_id=parent_task_id,
        )

    def get_messages_for_task(self, task_id: str) -> List[Dict[str, Any]]:
        return [m for m in self._messages if m.get("task_id") == task_id]

    def get_messages_for_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        return [m for m in self._messages if m.get("recipient_agent") in (agent_type, "BROADCAST")]
