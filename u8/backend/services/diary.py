"""
DiaryService - Retrieves diary summaries and life logs.
"""
from datetime import datetime, timezone, timedelta

from shared.data_access import DataAccess, SK_DAILY_FUREMARU_SUMMARY, SK_STRESS_SUMMARY


class DiaryService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()

    def get_diary_list(self, user_id: str, limit: int = 7) -> dict:
        """Get recent diary entries."""
        entries = self.da.query_by_prefix(f"USER#{user_id}", "DAILY_FUREMARU_SUMMARY#")

        # Sort by date descending
        sorted_entries = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)[:limit]

        return {
            "entries": [
                {
                    "date": e.get("date", ""),
                    "content": e.get("content", ""),
                    "life_log_count": e.get("life_log_count", 0),
                }
                for e in sorted_entries
            ]
        }

    def get_diary_detail(self, user_id: str, date: str) -> dict:
        """Get detailed diary for a specific date."""
        # Get diary
        sk = SK_DAILY_FUREMARU_SUMMARY.format(date=date)
        diary = self.da.get_item(f"USER#{user_id}", sk)

        if not diary:
            return {"date": date, "content": None, "life_logs": [], "stress": None}

        # Get life logs for the date
        life_logs = self.da.query_by_prefix(f"USER#{user_id}", f"LIFE_LOG#{date}")

        # Get stress for the date
        stress_sk = SK_STRESS_SUMMARY.format(date=date)
        stress_item = self.da.get_item(f"USER#{user_id}", stress_sk)
        stress = None
        if stress_item:
            stress = {
                "level": stress_item.get("stress_level"),
                "mood": stress_item.get("mood", ""),
            }

        return {
            "date": date,
            "content": diary.get("content", ""),
            "life_log_count": diary.get("life_log_count", 0),
            "life_logs": [
                {"category": l.get("category", ""), "content": l.get("content", "")}
                for l in life_logs
            ],
            "stress": stress,
        }
