import pytest
from autotimetabler import MinuteInterval


@pytest.fixture()
def minute_interval_instance():
    wk = MinuteInterval()
    yield wk


def test_day_hour_interval_to_minute_interval(minute_interval_instance):
    """
        Tests for the case where day-hour format is given, and we are looking for the minute interval format.
            :param minute_interval_instance:
            :return:
    """
    assert minute_interval_instance.map_day_hour_to_minute_interval([1, 12, 15]) == [720, 900]
    assert minute_interval_instance.map_day_hour_to_minute_interval([2, 12, 15]) == [2160, 2340]
    assert minute_interval_instance.map_day_hour_to_minute_interval([3, 12, 15]) == [3600, 3780]
    assert minute_interval_instance.map_day_hour_to_minute_interval([4, 12, 15]) == [5040, 5220]
    assert minute_interval_instance.map_day_hour_to_minute_interval([5, 12, 15]) == [6480, 6660]
    assert minute_interval_instance.map_day_hour_to_minute_interval([1, 12.5, 15.25]) == [750, 915]
    assert minute_interval_instance.map_day_hour_to_minute_interval([2, 12.2, 15.75]) == [2172, 2385]
    assert minute_interval_instance.map_day_hour_to_minute_interval([5, 12.25, 15.50]) == [6495, 6690]


def test_minute_interval_to_hour_interval(minute_interval_instance):
    assert minute_interval_instance.map_minute_interval_to_day_hour([720, 900]) == [1, 12, 15]
    assert minute_interval_instance.map_minute_interval_to_day_hour([2160, 2340]) == [2, 12, 15]
    assert minute_interval_instance.map_minute_interval_to_day_hour([5040, 5220]) == [4, 12, 15]
    assert minute_interval_instance.map_minute_interval_to_day_hour([6480, 6660]) == [5, 12, 15]
    assert minute_interval_instance.map_minute_interval_to_day_hour([750, 915]) == [1, 12.5, 15.25]
    assert minute_interval_instance.map_minute_interval_to_day_hour([2172, 2385]) == [2, 12.2, 15.75]
    assert minute_interval_instance.map_minute_interval_to_day_hour([6495, 6690]) == [5, 12.25, 15.50]
