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


def test_race_results_list_the_seasons_races_in_round_order(db, monza, make_race):
    make_race(season=2023, round=15, name="Singapore Grand Prix", circuit_ref="marina_bay")
    make_race(season=2023, round=2, name="Saudi Arabian Grand Prix", circuit_ref="jeddah")
    make_race(season=2022, round=1, name="Bahrain Grand Prix", circuit_ref="bahrain")

    output = run_tool(db, "get_race_results", {"season": 2023, "race": "monza"})

    assert output["season_races"] == [
        "round 2: Saudi Arabian Grand Prix (jeddah)",
        "round 14: Italian Grand Prix (monza)",
        "round 15: Singapore Grand Prix (marina_bay)",
    ]


def test_race_results_description_mentions_the_season_race_list():
    description = next(t for t in TOOLS if t["name"] == "get_race_results")["description"]
    assert "season_races" in description


def test_race_matches_circuit_ref_case_insensitively(db, monza):
    output = run_tool(db, "get_race_results", {"season": 2023, "race": "MONZA"})

    assert output["race"]["round"] == 14


def test_race_matches_name_substring(db, monza):
    output = run_tool(db, "get_race_results", {"season": 2023, "race": "italian"})

    assert output["race"]["name"] == "Italian Grand Prix"


def test_race_matches_round_number_string(db, monza):
    output = run_tool(db, "get_race_results", {"season": 2023, "race": "14"})

    assert output["race"]["name"] == "Italian Grand Prix"


def test_exact_circuit_match_wins_over_name_substring(db, make_race):
    make_race(season=2024, round=14, name="Belgian Grand Prix", circuit_ref="spa")
    make_race(season=2024, round=10, name="Spanish Grand Prix", circuit_ref="catalunya")

    output = run_tool(db, "get_race_results", {"season": 2024, "race": "spa"})

    assert output["race"]["name"] == "Belgian Grand Prix"


def test_name_substring_is_used_when_nothing_matches_exactly(db, make_race):
    make_race(season=2024, round=10, name="Spanish Grand Prix", circuit_ref="catalunya")
    make_race(season=2024, round=14, name="Belgian Grand Prix", circuit_ref="spa")

    output = run_tool(db, "get_race_results", {"season": 2024, "race": "span"})

    assert output["race"]["name"] == "Spanish Grand Prix"


def test_whole_race_name_is_an_exact_match(db, make_race):
    make_race(season=2024, round=1, name="British Grand Prix", circuit_ref="silverstone")
    make_race(season=2024, round=2, name="Grand Prix", circuit_ref="elsewhere")

    output = run_tool(db, "get_race_results", {"season": 2024, "race": "grand prix"})

    assert output["race"]["round"] == 2


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


def test_exact_driver_code_wins_over_name_substring(db, monza, make_driver, make_result):
    # "ver" is Max's code and also sits inside "Oliver".
    make_result(monza[0], make_driver("bearman", "BEA", "Oliver Bearman"), position=3)

    output = run_tool(db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "VER"})

    assert output["driver"] == "Max Verstappen"


def test_driver_name_substring_is_used_when_nothing_matches_exactly(
    db, monza, make_driver, make_result
):
    make_result(monza[0], make_driver("bearman", "BEA", "Oliver Bearman"), position=3)

    output = run_tool(db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "bear"})

    assert output["driver"] == "Oliver Bearman"


def test_drivers_sharing_a_surname_are_still_ambiguous(db, monza, make_driver, make_result):
    make_result(
        monza[0], make_driver("michael_schumacher", "MSC", "Michael Schumacher"), position=3
    )
    make_result(monza[0], make_driver("ralf_schumacher", "RSC", "Ralf Schumacher"), position=4)

    output = run_tool(
        db, "get_pit_strategy", {"season": 2023, "race": "monza", "driver": "schumacher"}
    )

    assert "More than one driver" in output["error"]


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
        "get_laps": {"season": 2023, "race": "monza", "driver": "ver"},
        "get_laps lap": {"season": 2023, "race": "monza", "lap": 1},
        "get_laps both": {"season": 2023, "race": "monza", "driver": "ver", "lap": 1},
        "get_championship_progression": {"season": 2023, "driver": "ver"},
    }

    for name, tool_input in calls.items():
        output = run_tool(db, name.split()[0], tool_input)
        assert "error" not in output
        json.dumps(output)


def test_every_tool_definition_matches_a_function_and_its_required_inputs(db):
    required_by_tool = {
        "get_race_results": ["season", "race"],
        "compare_drivers": ["season", "race", "driver_a", "driver_b"],
        "get_pit_strategy": ["season", "race", "driver"],
        "get_season_summary": ["season"],
        "get_laps": ["season", "race"],
        "get_championship_progression": ["season", "driver"],
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


# get_season_summary


@pytest.fixture
def season_2024(make_race, make_driver, make_result, make_sprint_result):
    """2024 rounds 1-3 plus a 2023 round. Verstappen: 1st, 2nd, withdrew (and won in 2023).
    Perez: 3rd, retired, 1st. Norris (McLaren): 2nd, 1st. Piastri (McLaren): 5th, disqualified."""
    r1 = make_race(season=2024, round=1, name="Bahrain Grand Prix")
    r2 = make_race(season=2024, round=2, name="Chinese Grand Prix")
    r3 = make_race(season=2024, round=3, name="Japanese Grand Prix")
    old = make_race(season=2023, round=1, name="Bahrain Grand Prix")
    ver = make_driver("max_verstappen", "VER", "Max Verstappen")
    per = make_driver("perez", "PER", "Sergio Pérez")
    nor = make_driver("norris", "NOR", "Lando Norris")
    pia = make_driver("piastri", "PIA", "Oscar Piastri")
    make_result(r1, ver, position=1, points=25, team="Red Bull")
    make_result(r1, per, position=3, points=15, team="Red Bull")
    make_result(r1, nor, position=2, points=18, team="McLaren")
    make_result(r1, pia, position=5, points=10, team="McLaren")
    make_result(r2, ver, position=2, points=18, team="Red Bull")
    make_result(r2, per, position=2, position_text="R", points=0, team="Red Bull")
    make_result(r2, nor, position=1, points=25, team="McLaren")
    make_result(r2, pia, position=1, position_text="D", points=0, team="McLaren")
    make_result(r3, ver, position=20, position_text="W", points=0, team="Red Bull")
    make_result(r3, per, position=1, points=25, team="Red Bull")
    make_result(old, ver, position=1, points=25, team="Red Bull")
    make_sprint_result(r2, ver, position=1, points=8, team="Red Bull")
    make_sprint_result(r2, nor, position=2, points=7, team="McLaren")


def test_driver_season_totals(db, season_2024):
    output = run_tool(db, "get_season_summary", {"season": 2024, "driver": "verstappen"})

    # The withdrawal (W) is not a start and the 2023 win is another season.
    assert output["driver"] == "Max Verstappen"
    assert output["season"] == 2024
    assert output["races"] == 2
    assert output["wins"] == 1
    assert output["podiums"] == 2
    assert output["retirements"] == 0
    # Sprint points go into sprint_points and total_points only.
    assert output["race_points"] == 43.0
    assert output["sprint_points"] == 8.0
    assert output["total_points"] == 51.0


def test_driver_season_lists_races_in_round_order_with_team(db, season_2024):
    output = run_tool(db, "get_season_summary", {"season": 2024, "driver": "VER"})

    assert output["results"] == [
        {
            "round": 1,
            "race": "Bahrain Grand Prix",
            "team": "Red Bull",
            "position_text": "1",
            "points": 25.0,
        },
        {
            "round": 2,
            "race": "Chinese Grand Prix",
            "team": "Red Bull",
            "position_text": "2",
            "points": 18.0,
        },
        {
            "round": 3,
            "race": "Japanese Grand Prix",
            "team": "Red Bull",
            "position_text": "W",
            "points": 0.0,
        },
    ]


def test_driver_season_counts_retirements_and_has_no_sprint_points_without_sprints(db, season_2024):
    output = run_tool(db, "get_season_summary", {"season": 2024, "driver": "perez"})

    assert output["driver"] == "Sergio Pérez"
    assert output["races"] == 3
    assert output["wins"] == 1
    assert output["podiums"] == 2
    assert output["retirements"] == 1
    assert output["sprint_points"] == 0.0
    assert output["total_points"] == 40.0


def test_team_totals_count_each_car(db, season_2024):
    output = run_tool(db, "get_season_summary", {"season": 2024, "team": "McLaren"})

    # Round 1: 2nd and 5th. Round 2: 1st and a disqualified car, which is no win or podium.
    assert output["team"] == "McLaren"
    assert output["races"] == 4
    assert output["wins"] == 1
    assert output["podiums"] == 2
    assert output["race_points"] == 53.0
    assert output["sprint_points"] == 7.0
    assert output["total_points"] == 60.0


def test_team_one_two_finish_is_one_win_and_two_podiums(db, make_race, make_driver, make_result):
    race = make_race(season=2022, round=1, name="Bahrain Grand Prix")
    make_result(race, make_driver("a", "AAA", "Driver A"), position=1, team="Ferrari")
    make_result(race, make_driver("b", "BBB", "Driver B"), position=2, team="Ferrari")

    output = run_tool(db, "get_season_summary", {"season": 2022, "team": "ferrari"})

    assert (output["wins"], output["podiums"], output["races"]) == (1, 2, 2)
    assert [(r["driver"], r["position_text"]) for r in output["results"]] == [
        ("Driver A", "1"),
        ("Driver B", "2"),
    ]


def test_description_says_team_totals_count_each_car():
    tool = next(t for t in TOOLS if t["name"] == "get_season_summary")

    assert "1-2 finish is 1 win and 2 podiums" in tool["description"]


def test_season_driver_match_ignores_accents_and_other_seasons(
    db, season_2024, make_driver, make_race, make_result
):
    # A driver named Perez who raced only in 2023 must not make "perez" ambiguous in 2024.
    make_result(make_race(season=2023, round=2), make_driver("other", "OTH", "Pedro Perez"))

    accented = run_tool(db, "get_season_summary", {"season": 2024, "driver": "Sergio Perez"})
    shared = run_tool(db, "get_season_summary", {"season": 2024, "driver": "perez"})

    assert accented["driver"] == "Sergio Pérez"
    assert shared["races"] == 3


def test_season_driver_not_found_lists_that_seasons_drivers(db, season_2024):
    output = run_tool(db, "get_season_summary", {"season": 2024, "driver": "hamilton"})

    assert "No driver matching 'hamilton' in 2024" in output["error"]
    assert "Lando Norris (NOR)" in output["error"]


def test_season_driver_ambiguous(db, season_2024, make_driver, make_race, make_result):
    make_result(make_race(season=2024, round=9), make_driver("jos", "JVE", "Jos Verstappen"))

    output = run_tool(db, "get_season_summary", {"season": 2024, "driver": "verstappen"})

    assert "More than one driver" in output["error"]
    assert "Jos Verstappen (JVE)" in output["error"]


def test_team_match_ignores_case_and_accents(db, make_race, make_driver, make_result):
    make_result(make_race(season=2024, round=1), make_driver(), team="Alpine Rénault")

    output = run_tool(db, "get_season_summary", {"season": 2024, "team": "RENAULT"})

    assert output["team"] == "Alpine Rénault"


def test_exact_team_match_wins_over_substring(db, make_race, make_driver, make_result):
    race = make_race(season=2024, round=1)
    make_result(race, make_driver("a", "AAA", "Driver A"), team="Red Bull")
    make_result(race, make_driver("b", "BBB", "Driver B"), position=2, team="Red Bull Racing")

    output = run_tool(db, "get_season_summary", {"season": 2024, "team": "red bull"})

    assert output["team"] == "Red Bull"
    assert output["races"] == 1


def test_team_ambiguous_lists_that_seasons_teams(db, make_race, make_driver, make_result):
    race = make_race(season=2024, round=1)
    make_result(race, make_driver("a", "AAA", "Driver A"), team="Red Bull Racing")
    make_result(race, make_driver("b", "BBB", "Driver B"), position=2, team="Red Bull Honda")
    make_result(race, make_driver("c", "CCC", "Driver C"), position=3, team="Ferrari")

    output = run_tool(db, "get_season_summary", {"season": 2024, "team": "red bull"})

    assert "More than one team matching 'red bull' in 2024" in output["error"]
    assert "Ferrari, Red Bull Honda, Red Bull Racing" in output["error"]


def test_team_not_found_lists_that_seasons_teams(db, season_2024):
    output = run_tool(db, "get_season_summary", {"season": 2024, "team": "Ferrari"})

    assert "No team matching 'Ferrari' in 2024" in output["error"]
    assert "McLaren, Red Bull" in output["error"]


def test_season_summary_needs_exactly_one_of_driver_or_team(db, season_2024):
    for tool_input in ({"season": 2024}, {"season": 2024, "driver": "ver", "team": "Red Bull"}):
        output = run_tool(db, "get_season_summary", tool_input)

        assert output["error"] == "Give exactly one of driver or team."


def test_season_without_races_says_so(db):
    for who in ({"driver": "verstappen"}, {"team": "Red Bull"}):
        output = run_tool(db, "get_season_summary", {"season": 1999, **who})

        assert "no results loaded for that season" in output["error"]


# get_laps


def laps_request(**fields):
    return {"season": 2023, "race": "monza", **fields}


def test_laps_by_driver_lists_laps_in_order_with_a_summary(db, monza, make_lap):
    race, ver, per = monza
    make_lap(race, ver, 3, "91.000", position=1, tire_type="HARD", tire_age=2)
    make_lap(race, ver, 1, "95.000", position=2, tire_type="MEDIUM", tire_age=0)
    make_lap(race, ver, 2, "92.500", position=1, tire_type="MEDIUM", tire_age=1)
    make_lap(race, per, 1, "80.000", position=1)

    output = run_tool(db, "get_laps", laps_request(driver="verstappen"))

    assert output["driver"] == "Max Verstappen"
    assert output["race"]["name"] == "Italian Grand Prix"
    assert output["laps"] == [
        {
            "lap": 1,
            "time": 95.0,
            "pos": 2,
            "tire": "MEDIUM",
            "tire_age": 0,
            "pit_out": False,
            "deleted": False,
        },
        {
            "lap": 2,
            "time": 92.5,
            "pos": 1,
            "tire": "MEDIUM",
            "tire_age": 1,
            "pit_out": False,
            "deleted": False,
        },
        {
            "lap": 3,
            "time": 91.0,
            "pos": 1,
            "tire": "HARD",
            "tire_age": 2,
            "pit_out": False,
            "deleted": False,
        },
    ]
    assert output["summary"] == {
        "laps": 3,
        "fastest_clean_lap": {"lap": 3, "time": 91.0},
        "deleted_laps": [],
    }


def test_laps_summary_skips_pit_out_deleted_and_untimed_laps(db, monza, make_lap):
    race, ver, _ = monza
    make_lap(race, ver, 1, "70.000", is_pit_out_lap=True)
    make_lap(race, ver, 2, "71.000", is_deleted=True)
    make_lap(race, ver, 3, None)
    make_lap(race, ver, 4, "90.000")
    make_lap(race, ver, 5, "89.000")
    make_lap(race, ver, 6, "60.000", is_deleted=True)

    output = run_tool(db, "get_laps", laps_request(driver="ver"))

    assert output["summary"] == {
        "laps": 6,
        "fastest_clean_lap": {"lap": 5, "time": 89.0},
        "deleted_laps": [2, 6],
    }
    assert output["laps"][2]["time"] is None


def test_laps_summary_without_any_clean_lap(db, monza, make_lap):
    race, ver, _ = monza
    make_lap(race, ver, 1, None)

    output = run_tool(db, "get_laps", laps_request(driver="ver"))

    assert output["summary"]["fastest_clean_lap"] is None


def test_laps_by_lap_gives_the_running_order_with_null_positions_last(
    db, monza, make_lap, make_driver, make_result
):
    race, ver, per = monza
    ham = make_driver("hamilton", "HAM", "Lewis Hamilton")
    make_result(race, ham, position=3)
    make_lap(race, per, 4, "91.000", position=2, tire_type="SOFT")
    make_lap(race, ham, 4, None, position=None)
    make_lap(race, ver, 4, "90.000", position=1, tire_type="MEDIUM")
    make_lap(race, ver, 5, "89.000", position=2)

    output = run_tool(db, "get_laps", laps_request(lap=4))

    assert output["lap"] == 4
    assert output["running_order"] == [
        {"pos": 1, "driver": "Max Verstappen", "code": "VER", "time": 90.0, "tire": "MEDIUM"},
        {"pos": 2, "driver": "Sergio Perez", "code": "PER", "time": 91.0, "tire": "SOFT"},
        {"pos": None, "driver": "Lewis Hamilton", "code": "HAM", "time": None, "tire": None},
    ]


def test_laps_with_driver_and_lap_gives_that_one_lap(db, monza, make_lap):
    race, ver, per = monza
    make_lap(race, ver, 1, "95.000")
    make_lap(race, ver, 2, "92.000", position=3, tire_type="HARD", tire_age=7, is_deleted=True)
    make_lap(race, per, 2, "80.000")

    output = run_tool(db, "get_laps", laps_request(driver="ver", lap=2))

    assert output["driver"] == "Max Verstappen"
    assert output["lap"] == {
        "lap": 2,
        "time": 92.0,
        "pos": 3,
        "tire": "HARD",
        "tire_age": 7,
        "pit_out": False,
        "deleted": True,
    }
    assert "summary" not in output


def test_laps_beyond_the_race_says_how_many_laps_it_had(db, monza, make_lap):
    race, ver, per = monza
    make_lap(race, ver, 53)
    make_lap(race, per, 51)

    for lap in (54, 0):
        output = run_tool(db, "get_laps", laps_request(lap=lap))

        assert output["error"] == f"Lap {lap} does not exist: the race had 53 laps."


def test_laps_driver_who_retired_before_the_lap_has_no_such_lap(db, monza, make_lap):
    race, ver, per = monza
    make_lap(race, ver, 10)
    make_lap(race, per, 3)

    output = run_tool(db, "get_laps", laps_request(driver="perez", lap=10))

    assert output["error"] == "Sergio Perez has no lap 10 in this race."


def test_laps_needs_a_driver_or_a_lap(db, monza):
    output = run_tool(db, "get_laps", laps_request())

    assert output["error"] == "Give a driver, a lap number, or both."


def test_laps_unknown_driver_lists_the_races_drivers(db, monza, make_lap):
    make_lap(monza[0], monza[1], 1)

    output = run_tool(db, "get_laps", laps_request(driver="hamilton"))

    assert "No driver matching 'hamilton'" in output["error"]


def test_laps_without_lap_data_returns_race_info_and_a_note(
    db, make_race, make_driver, make_result
):
    race = make_race(season=2019, round=1, name="Australian Grand Prix", circuit_ref="albert_park")
    make_result(race, make_driver("hamilton", "HAM", "Lewis Hamilton"), position=2)

    for fields in ({"driver": "ham"}, {"lap": 1}):
        output = run_tool(db, "get_laps", {"season": 2019, "race": "australian", **fields})

        assert output["race"]["name"] == "Australian Grand Prix"
        assert "Lap data is not available" in output["note"]
        assert "laps" not in output
        assert "running_order" not in output


# get_championship_progression


@pytest.fixture
def title_fight(make_race, make_driver, make_result, make_sprint_result):
    """2024 rounds 1-3 (round 4 has no results yet) and a 2023 round.
    Round 1: Alpha 25 (win), Bravo 18, Charlie 15. Round 2 has a sprint (Bravo 8, Alpha 7)
    and Charlie missing; the race gives Bravo 25 (win) and Alpha 18.
    Round 3: Alpha 25 (win), Bravo 18, Charlie 15.
    Totals after each round: Alpha 25, 50, 75. Bravo 18, 51, 69. Charlie 15, 15, 30."""
    r1 = make_race(season=2024, round=1, name="Bahrain Grand Prix", date=datetime.date(2024, 3, 2))
    r2 = make_race(season=2024, round=2, name="Chinese Grand Prix", date=datetime.date(2024, 4, 21))
    r3 = make_race(season=2024, round=3, name="Japanese Grand Prix", date=datetime.date(2024, 5, 5))
    make_race(season=2024, round=4, name="Australian Grand Prix")
    old = make_race(season=2023, round=1, name="Bahrain Grand Prix")
    alpha = make_driver("alpha", "ALP", "Anna Alpha")
    bravo = make_driver("bravo", "BRA", "Ben Bravo")
    charlie = make_driver("charlie", "CHA", "Cara Charlie")
    make_result(r1, alpha, position=1, points=25)
    make_result(r1, bravo, position=2, points=18)
    make_result(r1, charlie, position=3, points=15)
    make_result(r2, bravo, position=1, points=25)
    make_result(r2, alpha, position=2, points=18)
    make_sprint_result(r2, bravo, position=1, points=8)
    make_sprint_result(r2, alpha, position=2, points=7)
    make_result(r3, alpha, position=1, points=25)
    make_result(r3, bravo, position=2, points=18)
    make_result(r3, charlie, position=3, points=15)
    make_result(old, bravo, position=1, points=25)


def test_progression_gives_each_round_with_race_and_sprint_points(db, title_fight):
    output = run_tool(db, "get_championship_progression", {"season": 2024, "driver": "bravo"})

    assert output["season"] == 2024
    assert output["driver"] == "Ben Bravo"
    # The sprint is in round 2's 33 (25 + 8). Round 4 has no results and the 2023 win is ignored.
    assert output["rounds"] == [
        {
            "round": 1,
            "race": "Bahrain Grand Prix",
            "date": "2024-03-02",
            "points": 18.0,
            "total_points": 18.0,
            "position": 2,
            "leader": "Anna Alpha",
            "leader_points": 25.0,
            "gap_to_leader": 7.0,
        },
        {
            "round": 2,
            "race": "Chinese Grand Prix",
            "date": "2024-04-21",
            "points": 33.0,
            "total_points": 51.0,
            "position": 1,
            "leader": "Ben Bravo",
            "leader_points": 51.0,
            "gap_to_leader": 0.0,
            "gap_to_second": 1.0,
        },
        {
            "round": 3,
            "race": "Japanese Grand Prix",
            "date": "2024-05-05",
            "points": 18.0,
            "total_points": 69.0,
            "position": 2,
            "leader": "Anna Alpha",
            "leader_points": 75.0,
            "gap_to_leader": 6.0,
        },
    ]


def test_progression_shows_a_lead_change_from_the_other_side(db, title_fight):
    output = run_tool(db, "get_championship_progression", {"season": 2024, "driver": "ALP"})

    # Alpha leads after round 1, loses the lead by 1 point in round 2, and wins it back.
    assert [(r["position"], r["gap_to_leader"]) for r in output["rounds"]] == [
        (1, 0.0),
        (2, 1.0),
        (1, 0.0),
    ]
    assert output["rounds"][0]["gap_to_second"] == 7.0
    assert output["rounds"][1]["leader"] == "Ben Bravo"
    assert output["rounds"][2]["gap_to_second"] == 6.0


def test_progression_carries_points_over_a_round_the_driver_missed(db, title_fight):
    output = run_tool(db, "get_championship_progression", {"season": 2024, "driver": "charlie"})

    # Charlie has no result in round 2 (0 points, still 15 in total).
    assert [(r["points"], r["total_points"], r["position"]) for r in output["rounds"]] == [
        (15.0, 15.0, 3),
        (0.0, 15.0, 3),
        (15.0, 30.0, 3),
    ]
    assert [r["gap_to_leader"] for r in output["rounds"]] == [10.0, 36.0, 45.0]
    assert output["rounds"][1]["leader"] == "Ben Bravo"


def test_progression_ties_are_broken_by_wins_and_then_shared(
    db, make_race, make_driver, make_result, make_sprint_result
):
    # X and Y both have 37 points: X won a race (25 + 12) and Y did not (15 + 18 + 4 sprint).
    # Z and W also tie on 10 points with no win each, so they share 3rd.
    r1 = make_race(season=2022, round=1)
    r2 = make_race(season=2022, round=2)
    x, y = make_driver("x", "XXX", "Driver X"), make_driver("y", "YYY", "Driver Y")
    z, w = make_driver("z", "ZZZ", "Driver Z"), make_driver("w", "WWW", "Driver W")
    make_result(r1, x, position=1, points=25)
    make_result(r1, y, position=3, points=15)
    make_result(r1, z, position=5, points=10)
    make_result(r2, y, position=2, points=18)
    make_result(r2, x, position=4, points=12)
    make_result(r2, w, position=6, points=10)
    make_sprint_result(r2, y, position=5, points=4)

    rows = {
        name: run_tool(db, "get_championship_progression", {"season": 2022, "driver": name})[
            "rounds"
        ][-1]
        for name in ("XXX", "YYY", "ZZZ", "WWW")
    }

    assert (rows["XXX"]["position"], rows["XXX"]["gap_to_leader"]) == (1, 0.0)
    assert rows["XXX"]["gap_to_second"] == 0.0
    assert (rows["YYY"]["position"], rows["YYY"]["gap_to_leader"]) == (2, 0.0)
    assert rows["YYY"]["leader"] == "Driver X"
    assert rows["ZZZ"]["position"] == rows["WWW"]["position"] == 3


def test_progression_unknown_driver_lists_that_seasons_drivers(db, title_fight):
    output = run_tool(db, "get_championship_progression", {"season": 2024, "driver": "hamilton"})

    assert "No driver matching 'hamilton' in 2024" in output["error"]
    assert "Anna Alpha (ALP)" in output["error"]


def test_progression_description_covers_lead_and_gap_questions():
    description = next(t for t in TOOLS if t["name"] == "get_championship_progression")[
        "description"
    ]

    assert "took the lead" in description
    assert "gap to the leader" in description
    assert "ranked by wins" in description
