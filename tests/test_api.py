"""Endpoint tests. Expected values come from the rules in DESIGN.md and docs/schema.md."""

import datetime

import pytest

# /health


def test_health_says_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# /races


def test_races_is_empty_list_when_no_races(client):
    response = client.get("/races")

    assert response.status_code == 200
    assert response.json() == []


def test_races_returns_every_field(client, make_race):
    race = make_race(
        season=2023,
        round=14,
        name="Italian Grand Prix",
        date=datetime.date(2023, 9, 3),
        circuit_ref="monza",
        openf1_session_key=9161,
    )

    response = client.get("/races")

    assert response.json() == [
        {
            "id": race.id,
            "season": 2023,
            "round": 14,
            "name": "Italian Grand Prix",
            "date": "2023-09-03",
            "circuit_ref": "monza",
            "openf1_session_key": 9161,
            "winner": None,
            "has_sprint": False,
        }
    ]


def test_races_without_openf1_session_have_null_key(client, make_race):
    make_race(season=2010, round=1)

    assert client.get("/races").json()[0]["openf1_session_key"] is None


def test_races_are_ordered_by_season_then_round(client, make_race):
    make_race(season=2024, round=2)
    make_race(season=2023, round=10)
    make_race(season=2024, round=1)
    make_race(season=2023, round=2)

    body = client.get("/races").json()

    assert [(r["season"], r["round"]) for r in body] == [
        (2023, 2),
        (2023, 10),
        (2024, 1),
        (2024, 2),
    ]


def test_races_season_filter(client, make_race):
    make_race(season=2023, round=1)
    make_race(season=2024, round=1)
    make_race(season=2024, round=2)

    body = client.get("/races", params={"season": 2024}).json()

    assert [(r["season"], r["round"]) for r in body] == [(2024, 1), (2024, 2)]


def test_races_season_with_no_races_is_empty(client, make_race):
    make_race(season=2024)

    assert client.get("/races", params={"season": 1999}).json() == []


def test_races_rejects_non_numeric_season(client):
    assert client.get("/races", params={"season": "abc"}).status_code == 422


def test_races_list_the_winner(client, make_race, make_driver, make_result):
    race = make_race(season=2023, round=1)
    make_result(race, make_driver("second", "SEC", "Second Driver"), position=2, team="Ferrari")
    make_result(
        race, make_driver("lando_norris", "NOR", "Lando Norris"), position=1, team="McLaren"
    )

    assert client.get("/races").json()[0]["winner"] == {
        "driver_name": "Lando Norris",
        "driver_code": "NOR",
        "team": "McLaren",
    }


def test_races_winner_is_null_without_results_and_the_race_stays_listed(
    client, make_race, make_driver, make_result
):
    played, future = make_race(round=1), make_race(round=2)
    make_result(played, make_driver("old", None, "Old Driver"), position=1, team="Lotus")

    body = client.get("/races", params={"season": 2024}).json()

    assert [r["id"] for r in body] == [played.id, future.id]
    assert body[0]["winner"] == {"driver_name": "Old Driver", "driver_code": None, "team": "Lotus"}
    assert body[1]["winner"] is None


def test_a_single_race_has_no_winner_field(client, make_race, make_driver, make_result):
    race = make_race()
    make_result(race, make_driver(), position=1)

    assert "winner" not in client.get(f"/races/{race.id}").json()


# /races/{race_id}


def test_race_unknown_is_404(client):
    response = client.get("/races/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Race not found"}


def test_race_returns_every_field(client, make_race):
    race = make_race(
        season=2025,
        round=12,
        name="British Grand Prix",
        date=datetime.date(2025, 7, 6),
        circuit_ref="silverstone",
        openf1_session_key=9947,
    )

    response = client.get(f"/races/{race.id}")

    assert response.status_code == 200
    assert response.json() == {
        "id": race.id,
        "season": 2025,
        "round": 12,
        "name": "British Grand Prix",
        "date": "2025-07-06",
        "circuit_ref": "silverstone",
        "openf1_session_key": 9947,
    }


# CORS


def test_cors_allows_the_default_origin(client):
    response = client.get("/races", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_does_not_allow_an_unknown_origin(client):
    response = client.get("/races", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


# /races/{race_id}/results


def test_results_unknown_race_is_404(client):
    response = client.get("/races/999999/results")

    assert response.status_code == 404
    assert response.json() == {"detail": "Race not found"}


def test_results_race_with_no_results_is_empty(client, make_race):
    race = make_race()

    assert client.get(f"/races/{race.id}/results").json() == []


def test_results_include_driver_details(client, make_race, make_driver, make_result):
    race = make_race()
    driver = make_driver("lando_norris", "NOR", "Lando Norris")
    make_result(
        race,
        driver,
        driver_number=4,
        team="McLaren",
        grid=3,
        position=1,
        status="Finished",
        points=25,
    )

    body = client.get(f"/races/{race.id}/results").json()

    assert body == [
        {
            "driver_id": driver.id,
            "driver_code": "NOR",
            "driver_name": "Lando Norris",
            "driver_number": 4,
            "team": "McLaren",
            "grid": 3,
            "position": 1,
            "position_text": "1",
            "status": "Finished",
            "points": 25.0,
        }
    ]


def test_races_flag_sprint_weekends(client, make_race, make_driver, make_sprint_result):
    sprint_weekend = make_race(round=1)
    make_race(round=2)
    make_sprint_result(sprint_weekend, make_driver(), position=1, points=8)

    body = client.get("/races").json()

    assert [r["has_sprint"] for r in body] == [True, False]
    assert body[0]["winner"] is None  # A sprint win is not the race win.


def test_sprint_results_list_the_sprint_in_finishing_order(
    client, make_race, make_driver, make_result, make_sprint_result
):
    race = make_race()
    nor, pia = (
        make_driver("norris", "NOR", "Lando Norris"),
        make_driver("piastri", "PIA", "Oscar Piastri"),
    )
    make_sprint_result(race, pia, team="McLaren", grid=2, position=2, points=7)
    make_sprint_result(race, nor, team="McLaren", grid=1, position=1, points=8)
    make_result(race, pia, position=1, points=25)

    body = client.get(f"/races/{race.id}/sprint-results").json()

    assert [(r["driver_code"], r["position"], r["points"]) for r in body] == [
        ("NOR", 1, 8.0),
        ("PIA", 2, 7.0),
    ]


def test_sprint_results_are_empty_without_a_sprint_and_404_for_an_unknown_race(client, make_race):
    race = make_race()

    assert client.get(f"/races/{race.id}/sprint-results").json() == []
    assert client.get("/races/999999/sprint-results").status_code == 404


def test_results_are_ordered_by_finishing_position(client, make_race, make_driver, make_result):
    race = make_race()
    for ref, position in [("c", 3), ("a", 1), ("b", 2)]:
        make_result(race, make_driver(ref, None, ref), position=position)

    body = client.get(f"/races/{race.id}/results").json()

    assert [r["position"] for r in body] == [1, 2, 3]


def test_results_keep_fractional_points(client, make_race, make_driver, make_result):
    # The 2021 Belgian GP paid half points.
    race = make_race(season=2021)
    make_result(race, make_driver(), points="12.5")

    assert client.get(f"/races/{race.id}/results").json()[0]["points"] == 12.5


def test_results_allow_driver_without_code(client, make_race, make_driver, make_result):
    race = make_race(season=2000)
    make_result(race, make_driver("old_driver", None, "Old Driver"))

    assert client.get(f"/races/{race.id}/results").json()[0]["driver_code"] is None


def test_results_only_include_the_requested_race(client, make_race, make_driver, make_result):
    race, other = make_race(round=1), make_race(round=2)
    driver = make_driver()
    make_result(race, driver, points=25)
    make_result(other, driver, points=18)

    body = client.get(f"/races/{race.id}/results").json()

    assert [r["points"] for r in body] == [25.0]


# /races/{race_id}/laps


def test_laps_unknown_race_is_404(client):
    response = client.get("/races/999999/laps")

    assert response.status_code == 404
    assert response.json() == {"detail": "Race not found"}


def test_laps_unknown_driver_is_404(client, make_race):
    race = make_race()

    response = client.get(f"/races/{race.id}/laps", params={"driver_id": 999999})

    assert response.status_code == 404
    assert response.json() == {"detail": "Driver not found"}


def test_laps_race_without_lap_data_is_empty(client, make_race):
    # Races before 2023 have results but no laps.
    race = make_race(season=2010)

    assert client.get(f"/races/{race.id}/laps").json() == []


def test_laps_return_every_field(client, make_race, make_driver, make_lap):
    race = make_race()
    driver = make_driver()
    make_lap(
        race,
        driver,
        1,
        "95.123",
        tire_type="SOFT",
        tire_age=3,
        stint_number=1,
        position=2,
        is_pit_out_lap=False,
        is_deleted=True,
    )

    assert client.get(f"/races/{race.id}/laps").json() == [
        {
            "driver_id": driver.id,
            "lap_number": 1,
            "lap_time_seconds": 95.123,
            "tire_type": "SOFT",
            "tire_age": 3,
            "stint_number": 1,
            "position": 2,
            "is_pit_out_lap": False,
            "is_deleted": True,
        }
    ]


def test_laps_keep_laps_with_no_time(client, make_race, make_driver, make_lap):
    race = make_race()
    make_lap(race, make_driver(), 1, None)

    body = client.get(f"/races/{race.id}/laps").json()

    assert len(body) == 1
    assert body[0]["lap_time_seconds"] is None


def test_laps_are_ordered_by_driver_then_lap(client, make_race, make_driver, make_lap):
    race = make_race()
    first, second = make_driver("a", "AAA", "A"), make_driver("b", "BBB", "B")
    make_lap(race, second, 1)
    make_lap(race, first, 2)
    make_lap(race, second, 2)
    make_lap(race, first, 1)

    body = client.get(f"/races/{race.id}/laps").json()

    assert [(r["driver_id"], r["lap_number"]) for r in body] == [
        (first.id, 1),
        (first.id, 2),
        (second.id, 1),
        (second.id, 2),
    ]


def test_laps_driver_filter(client, make_race, make_driver, make_lap):
    race = make_race()
    wanted, other = make_driver("a", "AAA", "A"), make_driver("b", "BBB", "B")
    make_lap(race, wanted, 1)
    make_lap(race, other, 1)

    body = client.get(f"/races/{race.id}/laps", params={"driver_id": wanted.id}).json()

    assert [r["driver_id"] for r in body] == [wanted.id]


def test_laps_only_include_the_requested_race(client, make_race, make_driver, make_lap):
    race, other = make_race(round=1), make_race(round=2)
    driver = make_driver()
    make_lap(race, driver, 1, "90.000")
    make_lap(other, driver, 1, "80.000")

    body = client.get(f"/races/{race.id}/laps").json()

    assert [r["lap_time_seconds"] for r in body] == [90.0]


# /races/{race_id}/pit-stops


def test_pit_stops_unknown_race_is_404(client):
    response = client.get("/races/999999/pit-stops")

    assert response.status_code == 404
    assert response.json() == {"detail": "Race not found"}


def test_pit_stops_race_without_stops_is_empty(client, make_race):
    assert client.get(f"/races/{make_race().id}/pit-stops").json() == []


def test_pit_stops_return_every_field(client, make_race, make_driver, make_pit_stop):
    race = make_race()
    driver = make_driver()
    make_pit_stop(race, driver, 20, "25.760", "4.400")

    assert client.get(f"/races/{race.id}/pit-stops").json() == [
        {"driver_id": driver.id, "lap_number": 20, "lane_seconds": 25.76, "stationary_seconds": 4.4}
    ]


def test_pit_stops_allow_missing_stationary_time(client, make_race, make_driver, make_pit_stop):
    # Stationary times only exist from the 2024 US GP.
    race = make_race(season=2023)
    make_pit_stop(race, make_driver(), 20, "25.760", None)

    assert client.get(f"/races/{race.id}/pit-stops").json()[0]["stationary_seconds"] is None


def test_pit_stops_are_ordered_by_lap_then_driver(client, make_race, make_driver, make_pit_stop):
    race = make_race()
    first, second = make_driver("a", "AAA", "A"), make_driver("b", "BBB", "B")
    make_pit_stop(race, second, 30)
    make_pit_stop(race, second, 10)
    make_pit_stop(race, first, 30)

    body = client.get(f"/races/{race.id}/pit-stops").json()

    assert [(r["lap_number"], r["driver_id"]) for r in body] == [
        (10, second.id),
        (30, first.id),
        (30, second.id),
    ]


def test_pit_stops_only_include_the_requested_race(client, make_race, make_driver, make_pit_stop):
    race, other = make_race(round=1), make_race(round=2)
    driver = make_driver()
    make_pit_stop(race, driver, 10)
    make_pit_stop(other, driver, 40)

    body = client.get(f"/races/{race.id}/pit-stops").json()

    assert [r["lap_number"] for r in body] == [10]


# /drivers/{driver_id}/stats


def test_stats_unknown_driver_is_404(client):
    response = client.get("/drivers/999999/stats")

    assert response.status_code == 404
    assert response.json() == {"detail": "Driver not found"}


def test_stats_driver_with_no_results_is_all_zero(client, make_driver):
    driver = make_driver("lando_norris", "NOR", "Lando Norris")

    assert client.get(f"/drivers/{driver.id}/stats").json() == {
        "driver_id": driver.id,
        "driver_ref": "lando_norris",
        "code": "NOR",
        "full_name": "Lando Norris",
        "races": 0,
        "wins": 0,
        "points": 0.0,
        "average_lap_time_seconds": None,
    }


def test_stats_count_races_and_wins(client, make_race, make_driver, make_result):
    driver = make_driver()
    make_result(make_race(round=1), driver, position=1)
    make_result(make_race(round=2), driver, position=1)
    make_result(make_race(round=3), driver, position=5)

    body = client.get(f"/drivers/{driver.id}/stats").json()

    assert (body["races"], body["wins"]) == (3, 2)


def test_stats_do_not_count_withdrawals_as_races(client, make_race, make_driver, make_result):
    # Jolpica gives a driver who withdrew a numeric position, but they never started.
    driver = make_driver()
    make_result(make_race(round=1), driver, position=3)
    make_result(make_race(round=2), driver, position=20, position_text="W", status="Withdrew")

    assert client.get(f"/drivers/{driver.id}/stats").json()["races"] == 1


def test_stats_count_retirements_and_disqualifications_as_races_not_wins(
    client, make_race, make_driver, make_result
):
    driver = make_driver()
    make_result(make_race(round=1), driver, position=18, position_text="R", status="Retired")
    # A disqualified winner keeps a numeric position in some rows (Russell, Spa 2024).
    make_result(make_race(round=2), driver, position=1, position_text="D", status="Disqualified")

    body = client.get(f"/drivers/{driver.id}/stats").json()

    assert (body["races"], body["wins"]) == (2, 0)


def test_stats_points_add_sprint_points_to_race_points(
    client, make_race, make_driver, make_result, make_sprint_result
):
    driver = make_driver()
    race = make_race(round=1)
    make_result(race, driver, points=25)
    make_result(make_race(round=2), driver, points="12.5")
    make_sprint_result(race, driver, points=8)

    assert client.get(f"/drivers/{driver.id}/stats").json()["points"] == 45.5


def test_stats_sprints_are_not_races_or_wins(
    client, make_race, make_driver, make_result, make_sprint_result
):
    driver = make_driver()
    race = make_race()
    make_result(race, driver, position=4)
    make_sprint_result(race, driver, position=1)

    body = client.get(f"/drivers/{driver.id}/stats").json()

    assert (body["races"], body["wins"]) == (1, 0)


def test_stats_sprint_points_count_without_any_race_points(
    client, make_race, make_driver, make_sprint_result
):
    driver = make_driver()
    make_sprint_result(make_race(), driver, points=3)

    assert client.get(f"/drivers/{driver.id}/stats").json()["points"] == 3.0


@pytest.mark.parametrize(
    "excluded",
    [
        {"is_pit_out_lap": True},
        {"is_deleted": True},
        {"lap_time_seconds": None},
    ],
    ids=["pit-out-lap", "deleted-lap", "no-time"],
)
def test_stats_average_lap_uses_clean_laps_only(client, make_race, make_driver, make_lap, excluded):
    driver = make_driver()
    race = make_race()
    make_lap(race, driver, 1, "90.000")
    make_lap(race, driver, 2, "92.000")
    make_lap(race, driver, 3, **{"lap_time_seconds": "200.000", **excluded})

    assert client.get(f"/drivers/{driver.id}/stats").json()["average_lap_time_seconds"] == 91.0


def test_stats_average_lap_is_null_when_only_unclean_laps(client, make_race, make_driver, make_lap):
    driver = make_driver()
    make_lap(make_race(), driver, 1, "120.000", is_pit_out_lap=True)

    assert client.get(f"/drivers/{driver.id}/stats").json()["average_lap_time_seconds"] is None


def test_stats_ignore_other_drivers(
    client, make_race, make_driver, make_result, make_sprint_result, make_lap
):
    driver, rival = make_driver("a", "AAA", "A"), make_driver("b", "BBB", "B")
    race = make_race()
    make_result(race, driver, position=2, points=18)
    make_result(race, rival, position=1, points=25)
    make_sprint_result(race, rival, points=8)
    make_lap(race, driver, 1, "90.000")
    make_lap(race, rival, 1, "80.000")

    body = client.get(f"/drivers/{driver.id}/stats").json()

    assert (body["races"], body["wins"], body["points"], body["average_lap_time_seconds"]) == (
        1,
        0,
        18.0,
        90.0,
    )
