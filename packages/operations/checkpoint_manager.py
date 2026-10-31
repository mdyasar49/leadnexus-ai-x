from datetime import datetime, timezone
from typing import Dict, Any, Optional


class CheckpointManager:
    """
    Long-Running Collector Checkpoint Manager:
    - Maintains cursor positions (last page, last item, last timestamp)
    - Allows research campaigns to resume incrementally after restart without data loss
    """
    @classmethod
    def create_checkpoint(
        cls,
        source_key: str,
        cursor_data: Dict[str, Any],
        last_url: Optional[str] = None,
        items_processed: int = 0
    ) -> Dict[str, Any]:
        return {
            "source_key": source_key,
            "cursor_data": cursor_data,
            "last_url": last_url,
            "items_processed": items_processed,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

