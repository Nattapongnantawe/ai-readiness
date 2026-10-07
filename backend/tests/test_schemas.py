import pytest
from pydantic import ValidationError

from app.schemas import ScheduleIn, SearchIn


def test_interval_needs_hours():
    with pytest.raises(ValidationError):
        ScheduleIn(mode="interval")


def test_interval_minimum_one_hour():  # TC-04
    with pytest.raises(ValidationError):
        ScheduleIn(mode="interval", every_hours=0)


def test_daily_time_format():
    assert ScheduleIn(mode="daily", daily_at="02:00").daily_at == "02:00"
    with pytest.raises(ValidationError):
        ScheduleIn(mode="daily", daily_at="25:00")


def test_search_query_trimmed():
    assert SearchIn(query="  data engineer  ").query == "data engineer"
    with pytest.raises(ValidationError):
        SearchIn(query=" a ")
