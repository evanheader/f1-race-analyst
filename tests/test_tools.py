"""Tests for the AI analyst tools. Expected values come from the rules in DESIGN.md."""

import datetime
import json

import pytest

from app.tools import TOOLS, run_tool


@pytest.fixture
def monza(make_race, make_driver, make_result):
    """Monza 2023 with Verstappen winning and Perez second."""
    race = make_race(
        season=2023,
        round=14,
        name="Italian Grand Prix",
        date=datetime.date(2023, 9, 3),
        circuit_ref="monza",
    )
    ver = make_driver("max_verstappen", "VER", "Max Verstappen")
    per = make_driver("perez", "PER", "Sergio Perez")
    make_result(race, ver, position=1, grid=1, points=25, team="Red Bull")
    make_result(race, per, position=2, grid=3, points=18, team="Red Bull", driver_number=11)
    return race, ver, per


# get_race_results


def test_race_results_returns_race_and_ordered_results(db, monza):
    output = run_tool(db, "get_race_results", {"season": 2023, "race": "monza"})

    assert output["race"] == {
        "name": "Italian Grand Prix",
        "date": "2023-09-03",
        "circuit_ref": "monza",
        "season": 2023,
        "round": 14,
    }
    assert output["results"] == [
        {
            "position": 1,
            "position_text": "1",
            "driver": "Max Verstappen",
            "code": "VER",
            "team": "Red Bull",
            "grid": 1,
            "status": "Finished",
            "points": 25.0,
        },
        {
            "position": 2,
            "position_text": "2",
            "driver": "Sergio Perez",
            "code": "PER",
            "team": "Red Bull",
            "grid": 3,
            "status": "Finished",
            "points": 18.0,
        },
    ]


def test_race_matches_circuit_ref_case_insensitively(db, monza):
    output = run_tool(db, "get_race_results", {"season": 2023, "race": "MONZA"})

    assert output["race"]["round"] == 14


def test_race_matches_name_substring(db, monza):
    output = run_tool(db, "get_race_results", {"season": 2023, "race": "italian"})

    assert output["race"]["name"] == "Italian Grand Prix"


def test_race_matches_round_number_string(db, monza):
    output = run_tool(db, "get_race_results", {"season": 2023, "race": "14"})

    assert output["race"]["name"] == "Italian Grand Prix"


def test_race_not_found_lists_the_seasons_races(db, monza, make_race):
    make_race(season=2023, round=15, name="Singapore Grand Prix", circuit_ref="marina_bay")
    make_race(season=2022, round=1, name="Bahrain Grand Prix", circuit_ref="bahrain")

    output = run_tool(db, "get_race_results", {"season": 2023, "race": "imola"})

    assert "No race matching 'imola' in 2023" in output["error"]
    assert "Italian Grand Prix (monza)" in output["error"]
    assert "Singapore Grand Prix (marina_bay)" in output["error"]
    assert "Bahrain" not in output["error"]


def test_race_in_season_without_races_says_so(db):
    output = run_tool(db, "get_race_results", {"season": 1999, "race": "monza"})

    assert "no races loaded for that season" in output["error"]


def test_ambiguous_race_lists_candidates_with_rounds(db, make_race):
    make_race(season=2020, round=4, name="British Grand Prix", circuit_ref="silverstone")
    make_race(season=2020, round=5, name="70th Anniversary Grand Prix", circuit_ref="silverstone")

    output = run_tool(db, "get_race_results", {"season": 2020, "race": "silverstone"})

    assert "more than one race" in output["error"]
    assert "round 4: British Grand Prix" in output["error"]
    assert "round 5: 70th Anniversary Grand Prix" in output["error"]


# driver matching


def test_driver_matches_ref_code_or_name_substring(db, monza):
    for text in ("max_verstappen", "ver", "Max Verst"):
        output = run_tool(db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": text})
        assert output["driver"] == "Max Verstappen"


def test_driver_match_is_limited_to_the_races_entrants(db, monza, make_driver):
    # Jos Verstappen did not race at Monza 2023, so "verstappen" must mean Max.
    make_driver("jos_verstappen", "JVE", "Jos Verstappen")

    output = run_tool(
        db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "verstappen"}
    )

    assert output["driver"] == "Max Verstappen"


def test_ambiguous_driver_lists_the_races_drivers(db, monza, make_driver, make_result):
    race = monza[0]
    make_result(race, make_driver("jos_verstappen", "JVE", "Jos Verstappen"), position=3)

    output = run_tool(
        db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "verstappen"}
    )

    assert "More than one driver" in output["error"]
    assert "Max Verstappen (VER)" in output["error"]
    assert "Jos Verstappen (JVE)" in output["error"]


def test_driver_not_found_lists_the_races_drivers(db, monza):
    output = run_tool(
        db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "hamilton"}
    )

    assert "No driver matching 'hamilton'" in output["error"]
    assert "Max Verstappen (VER)" in output["error"]
    assert "Sergio Perez (PER)" in output["error"]


# compare_drivers


def test_compare_drivers_uses_clean_laps_only(db, monza, make_lap, make_pit_stop, make_driver):
    race, ver, per = monza
    # Verstappen: clean laps 90 and 92; the 120 out lap, 80 deleted lap and null lap are ignored.
    make_lap(race, ver, 1, "90.000")
    make_lap(race, ver, 2, "92.000")
    make_lap(race, ver, 3, "120.000", is_pit_out_lap=True)
    make_lap(race, ver, 4, "80.000", is_deleted=True)
    make_lap(race, ver, 5, None)
    make_pit_stop(race, ver, 3)
    make_lap(race, per, 1, "95.000")
    make_lap(race, per, 2, "93.000")
    make_pit_stop(race, per, 1)
    make_pit_stop(race, per, 2)

    output = run_tool(
        db,
        "compare_drivers",
        {"season": 2023, "race": "monza", "driver_a": "verstappen", "driver_b": "perez"},
    )

    assert output["drivers"] == [
        {
            "driver": "Max Verstappen",
            "position": 1,
            "position_text": "1",
            "status": "Finished",
            "laps_completed": 5,
            "average_clean_lap_seconds": 91.0,
            "fastest_clean_lap_seconds": 90.0,
            "pit_stops": 1,
        },
        {
            "driver": "Sergio Perez",
            "position": 2,
            "position_text": "2",
            "status": "Finished",
            "laps_completed": 2,
            "average_clean_lap_seconds": 94.0,
            "fastest_clean_lap_seconds": 93.0,
            "pit_stops": 2,
        },
    ]
    assert "note" not in output


def test_compare_drivers_without_lap_data_returns_results_and_a_note(
    db, make_race, make_driver, make_result
):
    race = make_race(season=2019, round=1, name="Australian Grand Prix", circuit_ref="albert_park")
    ham = make_driver("hamilton", "HAM", "Lewis Hamilton")
    bot = make_driver("bottas", "BOT", "Valtteri Bottas")
    make_result(race, ham, position=2, position_text="2")
    make_result(race, bot, position=20, position_text="R", status="Engine")

    output = run_tool(
        db,
        "compare_drivers",
        {"season": 2019, "race": "australian", "driver_a": "ham", "driver_b": "bot"},
    )

    assert output["drivers"] == [
        {"driver": "Lewis Hamilton", "position": 2, "position_text": "2", "status": "Finished"},
        {"driver": "Valtteri Bottas", "position": 20, "position_text": "R", "status": "Engine"},
    ]
    assert "Lap data is not available" in output["note"]


def test_compare_drivers_bad_driver_returns_error(db, monza):
    output = run_tool(
        db,
        "compare_drivers",
        {"season": 2023, "race": "monza", "driver_a": "verstappen", "driver_b": "nobody"},
    )

    assert "No driver matching 'nobody'" in output["error"]


# get_pit_strategy


def test_pit_strategy_returns_stints_and_stops(db, monza, make_lap, make_pit_stop):
    race, ver, _ = monza
    for lap in (1, 2, 3):
        make_lap(race, ver, lap, stint_number=1, tire_type="MEDIUM", tire_age=2 + lap - 1)
    for lap in (4, 5):
        make_lap(race, ver, lap, stint_number=2, tire_type="HARD", tire_age=0 + lap - 4)
    make_lap(race, ver, 6, None, stint_number=None)
    make_pit_stop(race, ver, 3, lane_seconds="22.500", stationary_seconds="2.400")
    make_pit_stop(race, ver, 4, lane_seconds="23.100")

    output = run_tool(
        db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "verstappen"}
    )

    assert output["starting_tire"] == "MEDIUM"
    assert output["stints"] == [
        {
            "stint": 1,
            "tire_type": "MEDIUM",
            "first_lap": 1,
            "last_lap": 3,
            "tire_age_at_first_lap": 2,
        },
        {
            "stint": 2,
            "tire_type": "HARD",
            "first_lap": 4,
            "last_lap": 5,
            "tire_age_at_first_lap": 0,
        },
    ]
    assert output["pit_stops"] == [
        {"lap": 3, "lane_seconds": 22.5, "stationary_seconds": 2.4},
        {"lap": 4, "lane_seconds": 23.1, "stationary_seconds": None},
    ]


def test_pit_strategy_ignores_other_drivers_laps(db, monza, make_lap):
    race, ver, per = monza
    make_lap(race, ver, 1, stint_number=1, tire_type="MEDIUM", tire_age=0)
    make_lap(race, per, 1, stint_number=1, tire_type="SOFT", tire_age=0)

    output = run_tool(db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "perez"})

    assert output["starting_tire"] == "SOFT"
    assert len(output["stints"]) == 1


def test_pit_strategy_without_lap_data_says_so(db, make_race, make_driver, make_result):
    race = make_race(season=2019, round=1, name="Australian Grand Prix")
    make_result(race, make_driver(), position=1)

    output = run_tool(
        db, "get_pit_strategy", {"season": 2019, "race": "australian", "driver": "verstappen"}
    )

    assert "not available" in output["note"]
    assert "stints" not in output


# run_tool


def test_unknown_tool_returns_error_listing_tools(db):
    output = run_tool(db, "get_weather", {})

    assert "Unknown tool 'get_weather'" in output["error"]
    assert "get_race_results" in output["error"]


def test_missing_input_returns_error(db):
    output = run_tool(db, "get_race_results", {"season": 2023})

    assert "Invalid input for get_race_results" in output["error"]


def test_output_is_json_serialisable(db, monza, make_lap, make_pit_stop):
    race, ver, per = monza
    make_lap(race, ver, 1, "90.123", stint_number=1, tire_type="SOFT", tire_age=0)
    make_pit_stop(race, ver, 1, stationary_seconds="2.5")
    make_lap(race, per, 1, "91.000")
    calls = {
        "get_race_results": {"season": 2023, "race": "monza"},
        "compare_drivers": {"season": 2023, "race": "monza", "driver_a": "ver", "driver_b": "per"},
        "get_pit_strategy": {"season": 2023, "race": "monza", "driver": "ver"},
    }

    for name, tool_input in calls.items():
        output = run_tool(db, name, tool_input)
        assert "error" not in output
        json.dumps(output)


def test_every_tool_definition_matches_a_function_and_its_required_inputs(db):
    required_by_tool = {
        "get_race_results": ["season", "race"],
        "compare_drivers": ["season", "race", "driver_a", "driver_b"],
        "get_pit_strategy": ["season", "race", "driver"],
    }

    assert {tool["name"] for tool in TOOLS} == set(required_by_tool)
    for tool in TOOLS:
        schema = tool["input_schema"]
        assert schema["required"] == required_by_tool[tool["name"]]
        assert set(schema["required"]) <= set(schema["properties"])
        assert tool["description"]
        # A known tool is dispatched: bad input gives an error about the input, not the name.
        assert "Unknown tool" not in run_tool(db, tool["name"], {}).get("error", "")


# accents and rounding


def test_driver_match_ignores_accents(db, make_race, make_driver, make_result):
    race = make_race(season=2023, round=1, name="Bahrain Grand Prix")
    make_result(race, make_driver("checo", "PER", "Sergio Pérez"), position=1)

    output = run_tool(
        db, "get_pit_strategy", {"season": 2023, "race": "bahrain", "driver": "Sergio Perez"}
    )

    assert output["driver"] == "Sergio Pérez"


def test_driver_full_name_substring_ignores_accents(db, make_race, make_driver, make_result):
    race = make_race(season=2023, round=1, name="Bahrain Grand Prix")
    make_result(race, make_driver("nico_h", "HUL", "Nico Hülkenberg"), position=1)

    output = run_tool(
        db, "get_pit_strategy", {"season": 2023, "race": "bahrain", "driver": "hulkenberg"}
    )

    assert output["driver"] == "Nico Hülkenberg"


def test_race_name_match_ignores_accents(db, make_race):
    make_race(season=2024, round=21, name="São Paulo Grand Prix", circuit_ref="interlagos")

    output = run_tool(db, "get_race_results", {"season": 2024, "race": "sao paulo"})

    assert output["race"]["circuit_ref"] == "interlagos"


def test_seconds_are_rounded_to_three_decimals(db, monza, make_lap):
    race, ver, per = monza
    for lap, time in enumerate(("90.000", "90.000", "91.000"), start=1):
        make_lap(race, ver, lap, time)
    make_lap(race, per, 1, "90.000")

    output = run_tool(
        db,
        "compare_drivers",
        {"season": 2023, "race": "monza", "driver_a": "ver", "driver_b": "per"},
    )

    assert output["drivers"][0]["average_clean_lap_seconds"] == 90.333
