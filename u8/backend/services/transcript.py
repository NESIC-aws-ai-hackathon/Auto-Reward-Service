"""
TranscriptService - Handles saving and managing conversation transcripts.
"""
from datetime import datetime, timezone

from shared.data_access import DataAccess, SK_CONVERSATION_TURN, SK_VOICE_SESSION


class TranscriptService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()

    def save_turn(self, user_id: str, session_id: str, turn: dict) -> dict:
        """Save a single conversation turn."""
        self._validate_turn(turn)

        timestamp = self._normalize_timestamp(turn["timestamp"])
        sk = SK_CONVERSATION_TURN.format(timestamp=timestamp)
        now = datetime.now(timezone.utc).isoformat()

        item = self.da.put_item(f"USER#{user_id}", sk, {
            "session_id": session_id,
            "role": turn["role"],
            "content": turn["content"],
            "turn_index": turn.get("turn_index", 0),
            "created_at": now,
        })

        return {"turn_id": sk}

    def save_bulk(self, user_id: str, session_id: str, turns: list[dict]) -> dict:
        """Save multiple conversation turns in batch."""
        if not turns:
            return {"saved_count": 0}
        if len(turns) > 100:
            raise ValueError("Maximum 100 turns per bulk request")

        items = []
        for i, turn in enumerate(turns):
            self._validate_turn(turn)
            timestamp = self._normalize_timestamp(turn["timestamp"])
            sk = SK_CONVERSATION_TURN.format(timestamp=timestamp)

            items.append({
                "PK": f"USER#{user_id}",
                "SK": sk,
                "session_id": session_id,
                "role": turn["role"],
                "content": turn["content"],
                "turn_index": turn.get("turn_index", i),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        self.da.batch_put(items)

        # Update turn_count on voice session
        voice_sk = SK_VOICE_SESSION.format(session_id=session_id)
        session = self.da.get_item(f"USER#{user_id}", voice_sk)
        if session:
            current_count = session.get("turn_count", 0)
            self.da.update_item(f"USER#{user_id}", voice_sk, {
                "turn_count": current_count + len(turns),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

        return {"saved_count": len(turns)}

    def get_session_turns(self, user_id: str, session_id: str) -> list[dict]:
        """Get all turns for a specific session."""
        turns = self.da.query_by_prefix(f"USER#{user_id}", "CONVERSATION_TURN#", limit=500)
        return [t for t in turns if t.get("session_id") == session_id]

    def _validate_turn(self, turn: dict) -> None:
        """Validate a single turn object."""
        if not turn.get("role") or turn["role"] not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        if not turn.get("content"):
            raise ValueError("content is required")
        if len(turn["content"]) > 10000:
            raise ValueError("content exceeds 10000 characters")
        if not turn.get("timestamp"):
            raise ValueError("timestamp is required")

    def _normalize_timestamp(self, ts: str) -> str:
        """Normalize timestamp to consistent ISO8601 format."""
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        except (ValueError, AttributeError):
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
