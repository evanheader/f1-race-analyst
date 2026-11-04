"""Loader tests. HTTP is faked, so nothing here touches the network.

Expected behavior comes from DESIGN.md ("Loading", "Cleaning decisions") and the
upstream API notes in docs/api-reference.md.
"""

import datetime
import json
from decimal import Decimal

import pytest
import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.models import Driver, Lap, PitStop, Race, Result, SprintResult
from scripts import load_data
from scripts.load_data import JOLPICA, OPENF1, RetryLater

# Fakes


class FakeResponse:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


@pytest.fixture
def http(monkeypatch, tmp_path):
    """Fake requests.get. Queue responses per URL; every request is recorded."""
    monkeypatch.setattr(load_data, "CACHE_DIR", tmp_path / "cache")
    sleeps = []
    monkeypatch.setattr(load_data.time, "sleep", sleeps.append)

    class Http:
        def __init__(self):
            self.responses = {}
            self.requests = []
            self.sleeps = sleeps

        def queue(self, url, *responses):
            self.responses.setdefault(url, []).extend(responses)

        def get(self, url, headers=None, timeout=None):
            self.requests.append((url, headers))
            return self.responses[url].pop(0)

    fake = Http()
    monkeypatch.setattr(load_data.requests, "get", fake.get)
    return fake


@pytest.fixture
def api(monkeypatch):
    """Fake get_json with a URL -> data map. An unexpected URL fails the test."""
    responses = {}
    monkeypatch.setattr(load_data, "get_json", lambda url, delay: responses[url])
    return responses


def jolpica_url(path, offset=0):
    return f"{JOLPICA}/{path}?limit=100&offset={offset}"


def jolpica_page(races, total=None, limit=100):
    return {
        "MRData": {
            "limit": str(limit),
            "total": str(len(races) if total is None else total),
            "RaceTable": {"Races": races},
        }
    }


def jolpica_race(season, round, date, circuit="monza", name="Italian Grand Prix", **extra):
    return {
        "season": str(season),
        "round": str(round),
        "raceName": name,
        "date": date,
        "Circuit": {"circuitId": circuit},
        **extra,
    }


def jolpica_result(ref, number, position, points="0", code=None, **fields):
    driver = {"driverId": ref, "givenName": ref.title(), "familyName": "Driver"}
    if code is not None:
        driver["code"] = code
    return {
        "number": str(number),
        "position": str(position),
        "positionText": fields.get("positionText", str(position)),
        "points": points,
        "grid": fields.get("grid", str(position)),
        "status": fields.get("status", "Finished"),
        "Driver": driver,
        "Constructor": {"name": fields.get("team", "McLaren")},
    }


def rows(connection, model):
    return connection.execute(select(model.__table__)).mappings().all()


def add_race(connection, season=2024, round=1, session_key=None):
    return connection.execute(
        insert(Race)
        .values(
            season=season,
            round=round,
            name="Test Grand Prix",
            date=datetime.date(season, 3, 1),
            circuit_ref="bahrain",
            openf1_session_key=session_key,
        )
        .returning(Race.__table__)
    ).one()


def add_driver(connection, ref):
    return connection.execute(
        insert(Driver).values(driver_ref=ref, code=None, full_name=ref).returning(Driver.id)
    ).scalar_one()


# get_json


def test_get_json_fetches_and_caches(http):
    url = f"{OPENF1}/laps?session_key=1"
    http.queue(url, FakeResponse(200, [{"lap_number": 1}]))

    assert load_data.get_json(url, 0) == [{"lap_number": 1}]
    assert load_data.get_json(url, 0) == [{"lap_number": 1}]
    assert len(http.requests) == 1


def test_get_json_reads_an_existing_cache_without_a_request(http):
    url = f"{OPENF1}/laps?session_key=1"
    http.queue(url, FakeResponse(200, ["first"]))
    load_data.get_json(url, 0)
    http.requests.clear()

    assert load_data.get_json(url, 0) == ["first"]
    assert http.requests == []


def test_get_json_cache_is_per_url(http):
    first, second = f"{OPENF1}/laps?session_key=1", f"{OPENF1}/laps?session_key=2"
    http.queue(first, FakeResponse(200, ["one"]))
    http.queue(second, FakeResponse(200, ["two"]))

    assert (load_data.get_json(first, 0), load_data.get_json(second, 0)) == (["one"], ["two"])


def test_get_json_sends_the_user_agent(http):
    # Jolpica requires a custom User-Agent.
    url = jolpica_url("2024/races/")
    http.queue(url, FakeResponse(200, {}))

    load_data.get_json(url, 0)

    assert http.requests[0][1]["User-Agent"].startswith("f1-race-analyst/")


def test_get_json_waits_before_a_request(http):
    url = jolpica_url("2024/races/")
    http.queue(url, FakeResponse(200, {}))

    load_data.get_json(url, 0.5)

    assert http.sleeps == [0.5]


def test_get_json_treats_404_as_empty_and_caches_it(http):
    # OpenF1 answers 404 "No results found." for an empty result.
    url = f"{OPENF1}/pit?session_key=1"
    http.queue(url, FakeResponse(404, {"detail": "No results found."}))

    assert load_data.get_json(url, 0) == []
    assert load_data.get_json(url, 0) == []
    assert len(http.requests) == 1


@pytest.mark.parametrize("status", [401, 429])
def test_get_json_jolpica_lockout_is_retry_later_and_not_cached(http, status):
    url = jolpica_url("2024/races/")
    http.queue(url, FakeResponse(status), FakeResponse(200, {"ok": True}))

    with pytest.raises(RetryLater):
        load_data.get_json(url, 0)
    assert load_data.get_json(url, 0) == {"ok": True}


def test_get_json_openf1_401_is_retry_later(http):
    # Free OpenF1 access returns 401 while a session is live.
    url = f"{OPENF1}/laps?session_key=1"
    http.queue(url, FakeResponse(401))

    with pytest.raises(RetryLater):
        load_data.get_json(url, 0)
    assert len(http.requests) == 1


def test_get_json_openf1_429_waits_and_retries(http):
    url = f"{OPENF1}/laps?session_key=1"
    http.queue(url, FakeResponse(429), FakeResponse(429), FakeResponse(200, ["ok"]))

    assert load_data.get_json(url, 0) == ["ok"]
    assert http.sleeps == [0, 5, 15]


def test_get_json_openf1_429_gives_up_after_three_retries(http):
    url = f"{OPENF1}/laps?session_key=1"
    http.queue(url, *[FakeResponse(429)] * 4)

    with pytest.raises(RetryLater):
        load_data.get_json(url, 0)
    assert len(http.requests) == 4


def test_get_json_server_error_raises_and_is_not_cached(http):
    url = jolpica_url("2024/races/")
    http.queue(url, FakeResponse(500), FakeResponse(200, {"ok": True}))

    with pytest.raises(requests.HTTPError):
        load_data.get_json(url, 0)
    assert load_data.get_json(url, 0) == {"ok": True}


def test_get_json_writes_valid_json_to_the_cache(http):
    url = f"{OPENF1}/laps?session_key=1"
    http.queue(url, FakeResponse(200, [{"lap_duration": 90.123}]))

    load_data.get_json(url, 0)

    [path] = list(load_data.CACHE_DIR.iterdir())
    assert json.loads(path.read_text()) == [{"lap_duration": 90.123}]


# jolpica_pages


def test_jolpica_pages_follows_offsets_until_total(api):
    api[jolpica_url("2024/results/", 0)] = jolpica_page([{"round": "1"}], total=150)
    api[jolpica_url("2024/results/", 100)] = jolpica_page([{"round": "2"}], total=150)

    assert load_data.jolpica_pages("2024/results/") == [{"round": "1"}, {"round": "2"}]


def test_jolpica_pages_steps_by_the_limit_the_server_returned(api):
    # MRData.limit may be lower than the 100 asked for.
    for offset in (0, 30, 60):
        api[jolpica_url("2024/results/", offset)] = jolpica_page(
            [{"offset": offset}], total=70, limit=30
        )

    assert load_data.jolpica_pages("2024/results/") == [
        {"offset": 0},
        {"offset": 30},
        {"offset": 60},
    ]


def test_jolpica_pages_empty_season(api):
    api[jolpica_url("2030/races/")] = jolpica_page([], total=0)

    assert load_data.jolpica_pages("2030/races/") == []


# load_races


def openf1_sessions_url(season):
    return f"{OPENF1}/sessions?year={season}&session_name=Race"


def test_load_races_converts_jolpica_fields(connection, api):
    api[jolpica_url("2023/races/")] = jolpica_page([jolpica_race(2023, 14, "2023-09-03")])
    api[openf1_sessions_url(2023)] = [
        {"date_start": "2023-09-03T13:00:00+00:00", "session_key": 9161}
    ]

    load_data.load_races(connection, 2023)

    [race] = rows(connection, Race)
    assert {k: v for k, v in race.items() if k != "id"} == {
        "season": 2023,
        "round": 14,
        "name": "Italian Grand Prix",
        "date": datetime.date(2023, 9, 3),
        "circuit_ref": "monza",
        "openf1_session_key": 9161,
    }


def test_load_races_matches_sessions_by_utc_date_not_time(connection, api):
    # Start times differ between the sources (Miami 2026: 17:00Z vs 20:00Z).
    api[jolpica_url("2026/races/")] = jolpica_page(
        [jolpica_race(2026, 6, "2026-05-03", time="20:00:00Z")]
    )
    api[openf1_sessions_url(2026)] = [
        {"date_start": "2026-05-03T17:00:00+00:00", "session_key": 11000}
    ]

    load_data.load_races(connection, 2026)

    assert rows(connection, Race)[0]["openf1_session_key"] == 11000


def test_load_races_matches_night_races_on_the_next_day(connection, api):
    # Las Vegas 2024 starts after midnight UTC in OpenF1.
    api[jolpica_url("2024/races/")] = jolpica_page([jolpica_race(2024, 22, "2024-11-23")])
    api[openf1_sessions_url(2024)] = [
        {"date_start": "2024-11-24T06:00:00+00:00", "session_key": 9644}
    ]

    load_data.load_races(connection, 2024)

    assert rows(connection, Race)[0]["openf1_session_key"] == 9644


def test_load_races_prefers_the_same_day_over_the_next_day(connection, api):
    api[jolpica_url("2024/races/")] = jolpica_page(
        [jolpica_race(2024, 1, "2024-03-02"), jolpica_race(2024, 2, "2024-03-03")]
    )
    api[openf1_sessions_url(2024)] = [
        {"date_start": "2024-03-02T15:00:00+00:00", "session_key": 1},
        {"date_start": "2024-03-03T15:00:00+00:00", "session_key": 2},
    ]

    load_data.load_races(connection, 2024)

    keys = {r["round"]: r["openf1_session_key"] for r in rows(connection, Race)}
    assert keys == {1: 1, 2: 2}


def test_load_races_unmatched_race_has_no_session_key(connection, api):
    api[jolpica_url("2024/races/")] = jolpica_page([jolpica_race(2024, 1, "2024-03-02")])
    api[openf1_sessions_url(2024)] = []

    load_data.load_races(connection, 2024)

    assert rows(connection, Race)[0]["openf1_session_key"] is None


def test_load_races_before_2023_does_not_ask_openf1(connection, api):
    # No OpenF1 URL is in the fake, so asking for one would raise KeyError.
    api[jolpica_url("2010/races/")] = jolpica_page([jolpica_race(2010, 1, "2010-03-14")])

    load_data.load_races(connection, 2010)

    assert rows(connection, Race)[0]["openf1_session_key"] is None


def test_load_races_rerun_updates_instead_of_duplicating(connection, api):
    api[openf1_sessions_url(2024)] = []
    api[jolpica_url("2024/races/")] = jolpica_page(
        [jolpica_race(2024, 1, "2024-03-02", name="Old")]
    )
    load_data.load_races(connection, 2024)
    api[jolpica_url("2024/races/")] = jolpica_page(
        [jolpica_race(2024, 1, "2024-03-02", name="New")]
    )

    load_data.load_races(connection, 2024)

    assert [r["name"] for r in rows(connection, Race)] == ["New"]


# load_results


def test_load_results_creates_drivers_and_results(connection, api):
    race = add_race(connection, 2021, 12)
    api[jolpica_url("2021/results/")] = jolpica_page(
        [
            {
                "round": "12",
                "Results": [
                    jolpica_result("max_verstappen", 33, 1, "12.5", code="VER", team="Red Bull"),
                    jolpica_result("old_timer", 99, 20, "0", positionText="R", status="Retired"),
                ],
            }
        ]
    )

    load_data.load_results(connection, 2021)

    drivers = {d["driver_ref"]: d for d in rows(connection, Driver)}
    assert drivers["max_verstappen"]["code"] == "VER"
    assert drivers["max_verstappen"]["full_name"] == "Max_Verstappen Driver"
    assert drivers["old_timer"]["code"] is None
    results = {r["driver_id"]: r for r in rows(connection, Result)}
    winner = results[drivers["max_verstappen"]["id"]]
    assert {k: v for k, v in winner.items() if k not in ("id", "driver_id")} == {
        "race_id": race.id,
        "driver_number": 33,
        "team": "Red Bull",
        "grid": 1,
        "position": 1,
        "position_text": "1",
        "status": "Finished",
        "points": Decimal("12.50"),
    }
    retired = results[drivers["old_timer"]["id"]]
    assert (retired["position_text"], retired["status"]) == ("R", "Retired")


def test_load_results_reuses_existing_drivers(connection, api):
    add_race(connection, 2024, 1)
    existing = add_driver(connection, "lando_norris")
    api[jolpica_url("2024/results/")] = jolpica_page(
        [{"round": "1", "Results": [jolpica_result("lando_norris", 4, 1, code="NOR")]}]
    )

    load_data.load_results(connection, 2024)

    assert [d["id"] for d in rows(connection, Driver)] == [existing]
    assert rows(connection, Result)[0]["driver_id"] == existing


def test_load_results_sprint_goes_to_sprint_results(connection, api):
    add_race(connection, 2024, 5)
    api[jolpica_url("2024/sprint/")] = jolpica_page(
        [{"round": "5", "SprintResults": [jolpica_result("lando_norris", 4, 1, "8")]}]
    )

    load_data.load_results(connection, 2024, sprint=True)

    assert rows(connection, Result) == []
    assert [r["points"] for r in rows(connection, SprintResult)] == [Decimal("8.00")]


def test_load_results_rerun_applies_post_race_penalties(connection, api):
    add_race(connection, 2024, 1)
    url = jolpica_url("2024/results/")
    api[url] = jolpica_page([{"round": "1", "Results": [jolpica_result("a", 1, 1, "25")]}])
    load_data.load_results(connection, 2024)
    api[url] = jolpica_page([{"round": "1", "Results": [jolpica_result("a", 1, 5, "10")]}])

    load_data.load_results(connection, 2024)

    [result] = rows(connection, Result)
    assert (result["position"], result["points"]) == (5, Decimal("10.00"))


def test_load_results_links_each_result_to_its_round(connection, api):
    first, second = add_race(connection, 2024, 1), add_race(connection, 2024, 2)
    api[jolpica_url("2024/results/")] = jolpica_page(
        [
            {"round": "2", "Results": [jolpica_result("a", 1, 1, "25")]},
            {"round": "1", "Results": [jolpica_result("a", 1, 3, "15")]},
        ]
    )

    load_data.load_results(connection, 2024)

    points = {r["race_id"]: r["points"] for r in rows(connection, Result)}
    assert points == {first.id: Decimal("15.00"), second.id: Decimal("25.00")}


# load_race_laps

SESSION = 9161


def openf1_lap(car, number, duration=90.0, start=None, pit_out=False):
    return {
        "driver_number": car,
        "lap_number": number,
        "lap_duration": duration,
        "date_start": start,
        "is_pit_out_lap": pit_out,
    }


def openf1_data(api, laps=(), stints=(), positions=(), control=(), pits=()):
    for endpoint, data in [
        ("laps", laps),
        ("stints", stints),
        ("position", positions),
        ("race_control", control),
        ("pit", pits),
    ]:
        api[f"{OPENF1}/{endpoint}?session_key={SESSION}"] = list(data)


@pytest.fixture
def race(connection):
    return add_race(connection, 2023, 14, session_key=SESSION)


@pytest.fixture
def driver(connection):
    return add_driver(connection, "max_verstappen")


def laps_by_number(connection):
    return {lap["lap_number"]: lap for lap in rows(connection, Lap)}


def test_load_race_laps_stores_lap_times(connection, api, race, driver):
    openf1_data(api, laps=[openf1_lap(1, 1, 95.123), openf1_lap(1, 2, None, pit_out=True)])

    load_data.load_race_laps(connection, race, {1: driver})

    laps = laps_by_number(connection)
    assert (laps[1]["race_id"], laps[1]["driver_id"]) == (race.id, driver)
    assert laps[1]["lap_time_seconds"] == Decimal("95.123")
    assert laps[1]["is_pit_out_lap"] is False
    # A lap with no time is kept with a null time.
    assert laps[2]["lap_time_seconds"] is None
    assert laps[2]["is_pit_out_lap"] is True


def test_load_race_laps_joins_tires_by_stint_lap_range(connection, api, race, driver):
    openf1_data(
        api,
        laps=[openf1_lap(1, n) for n in (1, 2, 3, 4)],
        stints=[
            {
                "driver_number": 1,
                "stint_number": 1,
                "lap_start": 1,
                "lap_end": 2,
                "compound": "SOFT",
                "tyre_age_at_start": 0,
            },
            {
                "driver_number": 1,
                "stint_number": 2,
                "lap_start": 3,
                "lap_end": 4,
                "compound": "HARD",
                "tyre_age_at_start": 3,
            },
        ],
    )

    load_data.load_race_laps(connection, race, {1: driver})

    laps = laps_by_number(connection)
    tires = {n: (lap["tire_type"], lap["stint_number"], lap["tire_age"]) for n, lap in laps.items()}
    # Tire age is tyre_age_at_start + (lap_number - lap_start).
    assert tires == {1: ("SOFT", 1, 0), 2: ("SOFT", 1, 1), 3: ("HARD", 2, 3), 4: ("HARD", 2, 4)}


def test_load_race_laps_open_stint_covers_later_laps(connection, api, race, driver):
    # OpenF1 leaves lap_end empty on a stint that hasn't ended.
    stint = {
        "driver_number": 1,
        "stint_number": 1,
        "lap_start": 1,
        "lap_end": None,
        "compound": "MEDIUM",
        "tyre_age_at_start": 0,
    }
    openf1_data(api, laps=[openf1_lap(1, 5)], stints=[stint])

    load_data.load_race_laps(connection, race, {1: driver})

    assert laps_by_number(connection)[5]["tire_type"] == "MEDIUM"


def test_load_race_laps_uses_only_the_cars_own_stints(connection, api, race, driver):
    other_car_stint = {
        "driver_number": 44,
        "stint_number": 1,
        "lap_start": 1,
        "lap_end": 10,
        "compound": "SOFT",
        "tyre_age_at_start": 0,
    }
    openf1_data(api, laps=[openf1_lap(1, 1)], stints=[other_car_stint])

    load_data.load_race_laps(connection, race, {1: driver})

    lap = laps_by_number(connection)[1]
    assert (lap["tire_type"], lap["stint_number"], lap["tire_age"]) == (None, None, None)


def test_load_race_laps_marks_deleted_laps(connection, api, race, driver):
    control = [
        {
            "date": "2023-09-03T13:10:00+00:00",
            "message": "CAR 1 (VER) TIME 1:25.000 DELETED - TRACK LIMITS AT TURN 1 LAP 2 15:10:00",
        }
    ]
    openf1_data(api, laps=[openf1_lap(1, 1), openf1_lap(1, 2, 85.0)], control=control)

    load_data.load_race_laps(connection, race, {1: driver})

    laps = laps_by_number(connection)
    assert (laps[1]["is_deleted"], laps[2]["is_deleted"]) == (False, True)


def test_load_race_laps_stores_position_at_lap_end(connection, api, race, driver):
    openf1_data(
        api,
        laps=[
            openf1_lap(1, 1, 90.0, "2023-09-03T13:00:00+00:00"),
            openf1_lap(1, 2, 90.0, "2023-09-03T13:01:30+00:00"),
        ],
        positions=[
            {"driver_number": 1, "date": "2023-09-03T12:55:00+00:00", "position": 3},
            {"driver_number": 44, "date": "2023-09-03T13:00:10+00:00", "position": 1},
            {"driver_number": 1, "date": "2023-09-03T13:02:00+00:00", "position": 2},
        ],
    )

    load_data.load_race_laps(connection, race, {1: driver})

    laps = laps_by_number(connection)
    assert (laps[1]["position"], laps[2]["position"]) == (3, 2)


def test_load_race_laps_skips_cars_not_in_the_results(connection, api, race, driver):
    openf1_data(
        api,
        laps=[openf1_lap(1, 1), openf1_lap(99, 1)],
        pits=[{"driver_number": 99, "lap_number": 1, "lane_duration": 25.0, "stop_duration": None}],
    )

    load_data.load_race_laps(connection, race, {1: driver})

    assert [lap["driver_id"] for lap in rows(connection, Lap)] == [driver]
    assert rows(connection, PitStop) == []


def test_load_race_laps_stores_pit_stops(connection, api, race, driver):
    openf1_data(
        api,
        pits=[
            {"driver_number": 1, "lap_number": 20, "lane_duration": 25.76, "stop_duration": 4.4},
            {"driver_number": 1, "lap_number": 40, "lane_duration": 22.1, "stop_duration": None},
        ],
    )

    load_data.load_race_laps(connection, race, {1: driver})

    stops = {
        s["lap_number"]: (s["race_id"], s["driver_id"], s["lane_seconds"], s["stationary_seconds"])
        for s in rows(connection, PitStop)
    }
    assert stops == {
        20: (race.id, driver, Decimal("25.760"), Decimal("4.400")),
        40: (race.id, driver, Decimal("22.100"), None),
    }


def test_load_race_laps_skips_pit_rows_without_a_lane_time(connection, api, race, driver):
    openf1_data(
        api,
        pits=[{"driver_number": 1, "lap_number": 20, "lane_duration": None, "stop_duration": None}],
    )

    load_data.load_race_laps(connection, race, {1: driver})

    assert rows(connection, PitStop) == []


def test_load_race_laps_repeated_pit_row_keeps_the_last(connection, api, race, driver):
    openf1_data(
        api,
        pits=[
            {"driver_number": 1, "lap_number": 20, "lane_duration": 30.0, "stop_duration": None},
            {"driver_number": 1, "lap_number": 20, "lane_duration": 25.0, "stop_duration": None},
        ],
    )

    load_data.load_race_laps(connection, race, {1: driver})

    assert [s["lane_seconds"] for s in rows(connection, PitStop)] == [Decimal("25.000")]


def test_load_race_laps_rerun_updates_instead_of_duplicating(connection, api, race, driver):
    pit = {"driver_number": 1, "lap_number": 1, "lane_duration": 25.0, "stop_duration": None}
    openf1_data(api, laps=[openf1_lap(1, 1, 90.0)], pits=[pit])
    load_data.load_race_laps(connection, race, {1: driver})
    openf1_data(api, laps=[openf1_lap(1, 1, 91.5)], pits=[{**pit, "lane_duration": 24.0}])

    load_data.load_race_laps(connection, race, {1: driver})

    assert [lap["lap_time_seconds"] for lap in rows(connection, Lap)] == [Decimal("91.500")]
    assert [s["lane_seconds"] for s in rows(connection, PitStop)] == [Decimal("24.000")]


def test_load_race_laps_with_no_data_writes_nothing(connection, api, race, driver):
    # Pit data is missing before the 2023 Spanish GP.
    openf1_data(api)

    load_data.load_race_laps(connection, race, {1: driver})

    assert (rows(connection, Lap), rows(connection, PitStop)) == ([], [])
