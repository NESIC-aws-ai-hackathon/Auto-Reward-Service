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

        # Get this month's expenses
        expenses = self.da.query_by_prefix(f"USER#{user_id}", "EXPENSE#")
        monthly_expenses = [
            e for e in expenses
            if e.get("created_at", "").startswith(month_prefix)
        ]
        total_spent = sum(e.get("amount", 0) for e in monthly_expenses)

        # Recent expenses (last 5)
        sorted_expenses = sorted(monthly_expenses, key=lambda e: e.get("created_at", ""), reverse=True)
        recent_expenses = [
            {
                "description": e.get("description", ""),
                "amount": e.get("amount", 0),
                "date": e.get("created_at", "")[:10],
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

        # Streak days (count consecutive days with voice sessions)
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
        """Count consecutive days with voice sessions (simplified)."""
        sessions = self.da.query_by_prefix(f"USER#{user_id}", "VOICE_SESSION#")
        if not sessions:
            return 0

        # Get unique dates from sessions
        dates_with_sessions = set()
        for s in sessions:
            created = s.get("created_at", "")
            if created:
                dates_with_sessions.add(created[:10])

        # Count consecutive days ending today
        streak = 0
        check_date = today
        for _ in range(30):  # Max 30 days
            date_str = check_date.strftime("%Y-%m-%d")
            if date_str in dates_with_sessions:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        return streak
