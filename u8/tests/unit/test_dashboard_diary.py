"""
Unit tests for DashboardService and DiaryService.
"""
import pytest
from unittest.mock import patch, MagicMock
import os

os.environ["TABLE_NAME"] = "ArsTable"
os.environ["AWS_REGION"] = "ap-northeast-1"
os.environ["ENV"] = "test"


@pytest.fixture
def mock_table():
    with patch("shared.data_access.boto3") as mock_boto:
        mock_tbl = MagicMock()
        mock_resource = MagicMock()
        mock_resource.Table.return_value = mock_tbl
        mock_boto.resource.return_value = mock_resource
        yield mock_tbl


class TestDashboardService:
    def test_returns_dashboard_data(self, mock_table):
        """Returns aggregated dashboard data."""
        # get_or_create_profile
        mock_table.get_item.side_effect = [
            {"Item": {"display_name": "太郎", "monthly_surplus": 10000}},
            {},  # stress summary not found
        ]
        # query_by_prefix calls
        mock_table.query.side_effect = [
            {"Items": [  # expenses
                {"amount": 450, "created_at": "2026-05-24T10:00:00Z", "description": "コーヒー"},
                {"amount": 980, "created_at": "2026-05-23T12:00:00Z", "description": "ランチ"},
            ]},
            {"Items": []},  # voice sessions
        ]

        from services.dashboard import DashboardService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = DashboardService(da)
        result = svc.get_dashboard("user-001")

        assert result["surplus"]["monthly_budget"] == 10000
        assert result["surplus"]["spent"] == 1430
        assert result["surplus"]["remaining"] == 8570
        assert len(result["recent_expenses"]) == 2

    def test_zero_budget_ratio_is_one(self, mock_table):
        """Zero budget returns ratio 1.0."""
        mock_table.get_item.side_effect = [
            {"Item": {"monthly_surplus": 0}},
            {},  # no stress
        ]
        mock_table.query.side_effect = [
            {"Items": []},  # no expenses
            {"Items": []},  # no sessions
        ]

        from services.dashboard import DashboardService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = DashboardService(da)
        result = svc.get_dashboard("user-001")

        assert result["surplus"]["ratio"] == 1.0


class TestDiaryService:
    def test_returns_diary_list(self, mock_table):
        """Returns diary entries sorted by date descending."""
        mock_table.query.return_value = {"Items": [
            {"date": "2026-05-22", "content": "diary 1", "life_log_count": 2},
            {"date": "2026-05-24", "content": "diary 3", "life_log_count": 4},
            {"date": "2026-05-23", "content": "diary 2", "life_log_count": 3},
        ]}

        from services.diary import DiaryService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = DiaryService(da)
        result = svc.get_diary_list("user-001")

        assert len(result["entries"]) == 3
        assert result["entries"][0]["date"] == "2026-05-24"
        assert result["entries"][2]["date"] == "2026-05-22"

    def test_diary_detail_with_logs(self, mock_table):
        """Returns diary detail with life logs and stress."""
        mock_table.get_item.side_effect = [
            {"Item": {"date": "2026-05-24", "content": "今日の太郎は...", "life_log_count": 2}},
            {"Item": {"stress_level": 3, "mood": "疲れ"}},
        ]
        mock_table.query.return_value = {"Items": [
            {"category": "場所", "content": "カフェ"},
            {"category": "支出", "content": "コーヒー 450円"},
        ]}

        from services.diary import DiaryService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = DiaryService(da)
        result = svc.get_diary_detail("user-001", "2026-05-24")

        assert result["content"] == "今日の太郎は..."
        assert len(result["life_logs"]) == 2
        assert result["stress"]["level"] == 3

    def test_diary_not_found(self, mock_table):
        """Returns empty when diary not found."""
        mock_table.get_item.return_value = {}

        from services.diary import DiaryService
        from shared.data_access import DataAccess

        da = DataAccess()
        svc = DiaryService(da)
        result = svc.get_diary_detail("user-001", "2026-01-01")

        assert result["content"] is None
        assert result["life_logs"] == []
