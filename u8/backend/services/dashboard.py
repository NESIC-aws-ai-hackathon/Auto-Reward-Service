"""
DashboardService - Aggregates data for the dashboard view.
"""
from datetime import datetime, timezone, timedelta

from shared.data_access import DataAccess, SK_STRESS_SUMMARY


class DashboardService:
    def __init__(self, da: DataAccess = None):
        self.da = da or DataAccess()

    def get_dashboard(self, user_id: str) -> dict:
        """Get dashboard data for the user."""
        jst = timezone(timedelta(hours=9))
        today = datetime.now(jst)
        today_str = today.strftime("%Y-%m-%d")
        month_prefix = today.strftime("%Y-%m")

        # Get profile
        profile = self.da.get_or_create_profile(user_id)
        monthly_budget = profile.get("monthly_surplus", 0)

        # Get this month's expenses (SK is EXPENSE#{iso_timestamp})
        expenses = self.da.query_by_prefix(f"USER#{user_id}", f"EXPENSE#{month_prefix}")
        total_spent = sum(int(e.get("amount", 0)) for e in expenses)

        # Recent expenses (last 5)
        sorted_expenses = sorted(expenses, key=lambda e: e.get("timestamp", e.get("SK", "")), reverse=True)
        recent_expenses = [
            {
                "description": e.get("item", e.get("description", "")),
                "amount": int(e.get("amount", 0)),
                "date": (e.get("timestamp", "") or "")[:10],
            }
            for e in sorted_expenses[:5]
        ]

        # Stress summary
        stress_sk = SK_STRESS_SUMMARY.format(date=today_str)
        stress_item = self.da.get_item(f"USER#{user_id}", stress_sk)
        stress = None
        if stress_item:
            stress = {
                "level": stress_item.get("stress_level"),
                "mood": stress_item.get("mood", ""),
                "date": today_str,
            }

        # Streak days (count consecutive days with life logs or chat)
        streak_days = self._calculate_streak(user_id, today)

        remaining = max(0, monthly_budget - total_spent)
        ratio = remaining / monthly_budget if monthly_budget > 0 else 1.0

        return {
            "surplus": {
                "monthly_budget": monthly_budget,
                "spent": total_spent,
                "remaining": remaining,
                "ratio": round(ratio, 2),
            },
            "stress": stress,
            "recent_expenses": recent_expenses,
            "streak_days": streak_days,
        }

    def _calculate_streak(self, user_id: str, today: datetime) -> int:
        """Count consecutive days with chat activity (life logs or chat messages)."""
        # Check life logs for activity
        logs = self.da.query_by_prefix(f"USER#{user_id}", "LIFE_LOG#")
        if not logs:
            # Fallback to chat messages
            chats = self.da.query_by_prefix(f"USER#{user_id}", "CHAT#")
            if not chats:
                return 0
            dates_with_activity = set()
            for c in chats:
                ts = c.get("timestamp", "")
                if ts:
                    dates_with_activity.add(ts[:10])
        else:
            dates_with_activity = set()
            for s in logs:
                date = s.get("date", "")
                if date:
                    dates_with_activity.add(date)

        # Count consecutive days ending today
        streak = 0
        check_date = today
        for _ in range(30):
            date_str = check_date.strftime("%Y-%m-%d")
            if date_str in dates_with_activity:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        return streak
