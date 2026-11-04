"""Tests for the loader's cleaning rules (DESIGN.md "Cleaning decisions"). No database needed.

Race control messages are copied from real OpenF1 responses.
"""

from scripts.load_data import deleted_laps, position_at_lap_ends


def message(text, date="2024-09-22T12:00:00+00:00"):
    return {"message": text, "date": date}


def lap(car, number, duration):
    return {"driver_number": car, "lap_number": number, "lap_duration": duration}


# deleted_laps


def test_no_messages_means_no_deleted_laps():
    assert deleted_laps([], [lap(5, 1, 90.0)]) == set()


def test_unrelated_messages_are_ignored():
    control = [
        message("GREEN LIGHT - PIT EXIT OPEN"),
        message("CAR 44 (HAM) TIME 1:32.123 NOTED - TRACK LIMITS AT TURN 4 LAP 12 14:03:22"),
    ]

    assert deleted_laps(control, [lap(44, 12, 92.123)]) == set()


def test_deleted_time_with_lap_number():
    control = [
        message("CAR 5 (BOR) TIME 1:53.937 DELETED - TRACK LIMITS AT TURN 11 LAP 2 14:03:22")
    ]

    assert deleted_laps(control, []) == {(5, 2)}


def test_deleted_lap_without_time_in_pit():
    control = [message("CAR 1 (NOR) LAP DELETED - TRACK LIMITS AT TURN 1 LAP 30 15:56:33 (PIT)")]

    assert deleted_laps(control, []) == {(1, 30)}


def test_deleted_at_pit_entry():
    control = [
        message("CAR 14 (ALO) TIME 1:36.320 DELETED - TRACK LIMITS AT PIT ENTRY LAP 6 14:13:01")
    ]

    assert deleted_laps(control, []) == {(14, 6)}


def test_next_lap_message_is_matched_by_lap_time():
    laps = [lap(16, 7, 95.001), lap(16, 8, 94.512), lap(16, 9, 95.4)]
    control = [message("CAR 16 (LEC) TIME 1:34.512 DELETED - TRACK LIMITS AT TURN 4 (NEXT LAP)")]

    assert deleted_laps(control, laps) == {(16, 8)}


def test_next_lap_message_only_matches_the_same_car():
    # Another car set the same time on a different lap.
    laps = [lap(55, 3, 94.512), lap(16, 8, 94.512)]
    control = [message("CAR 16 (LEC) TIME 1:34.512 DELETED - TRACK LIMITS AT TURN 4 (NEXT LAP)")]

    assert deleted_laps(control, laps) == {(16, 8)}


def test_next_lap_message_with_no_matching_time_deletes_nothing():
    control = [message("CAR 16 (LEC) TIME 1:34.512 DELETED - TRACK LIMITS AT TURN 4 (NEXT LAP)")]

    assert deleted_laps(control, [lap(16, 8, 94.513)]) == set()


def test_reinstated_time_clears_the_deletion():
    laps = [lap(44, 20, 72.028)]
    control = [
        message(
            "CAR 44 (HAM) TIME 1:12.028 DELETED - TRACK LIMITS AT TURN 9 LAP 20 15:20:00",
            "2024-09-22T12:00:00+00:00",
        ),
        message("CAR 44 (HAM) TIME 1:12.028 WILL BE REINSTATED", "2024-09-22T12:05:00+00:00"),
    ]

    assert deleted_laps(control, laps) == set()


def test_reinstated_lap_number_clears_the_deletion():
    # Singapore 2024 (session 9606): lap 1 deleted, then reinstated by lap number only.
    laps = [lap(55, 1, 105.2)]
    control = [
        message(
            "CAR 55 (SAI) LAP DELETED - TRACK LIMITS AT TURN 7 LAP 1 20:04:38",
            "2024-09-22T12:11:55+00:00",
        ),
        message("CAR 55 (SAI) LAP 1 WILL BE REINSTATED", "2024-09-22T12:12:20+00:00"),
    ]

    assert deleted_laps(control, laps) == set()


def test_reinstating_one_lap_keeps_other_deletions():
    control = [
        # Monza 2026 (session 11361).
        message(
            "CAR 55 (SAI) LAP DELETED - TRACK LIMITS AT TURN 5 LAP 1 15:04:11",
            "2026-09-06T13:08:30+00:00",
        ),
        message("CAR 55 (SAI) LAP 1 WILL BE REINSTATED", "2026-09-06T13:25:10+00:00"),
        message(
            "CAR 55 (SAI) TIME 1:26.235 DELETED - TRACK LIMITS AT TURN 5 LAP 39 16:35:07",
            "2026-09-06T14:36:10+00:00",
        ),
    ]

    assert deleted_laps(control, []) == {(55, 39)}


def test_messages_are_applied_in_time_order():
    # Given out of order, the deletion still comes before the reinstatement.
    laps = [lap(44, 20, 72.028)]
    control = [
        message("CAR 44 (HAM) TIME 1:12.028 WILL BE REINSTATED", "2024-09-22T12:05:00+00:00"),
        message(
            "CAR 44 (HAM) TIME 1:12.028 DELETED - TRACK LIMITS AT TURN 9 LAP 20 15:20:00",
            "2024-09-22T12:00:00+00:00",
        ),
    ]

    assert deleted_laps(control, laps) == set()


# position_at_lap_ends


def timed_lap(number, start, duration=90.0):
    return {"lap_number": number, "date_start": start, "lap_duration": duration}


def change(date, position):
    return {"date": date, "position": position}


def test_position_is_the_latest_change_before_the_next_lap_starts():
    laps = [
        timed_lap(1, "2024-01-01T14:00:00+00:00"),
        timed_lap(2, "2024-01-01T14:01:30+00:00"),
        timed_lap(3, "2024-01-01T14:03:00+00:00"),
    ]
    changes = [
        change("2024-01-01T13:55:00+00:00", 5),  # starting grid
        change("2024-01-01T14:00:40+00:00", 4),  # during lap 1
        change("2024-01-01T14:01:50+00:00", 3),  # during lap 2
        change("2024-01-01T14:02:10+00:00", 2),  # also during lap 2
    ]

    assert position_at_lap_ends(laps, changes) == {1: 4, 2: 2, 3: 2}


def test_change_exactly_at_the_lap_end_counts_for_that_lap():
    laps = [timed_lap(1, "2024-01-01T14:00:00+00:00"), timed_lap(2, "2024-01-01T14:01:30+00:00")]
    changes = [change("2024-01-01T13:55:00+00:00", 5), change("2024-01-01T14:01:30+00:00", 4)]

    assert position_at_lap_ends(laps, changes)[1] == 4


def test_last_lap_ends_at_its_start_plus_its_duration():
    laps = [timed_lap(1, "2024-01-01T14:00:00+00:00", 90.0)]
    changes = [
        change("2024-01-01T13:55:00+00:00", 5),
        change("2024-01-01T14:01:29+00:00", 4),  # before the line
        change("2024-01-01T14:01:31+00:00", 3),  # after the line
    ]

    assert position_at_lap_ends(laps, changes) == {1: 4}


def test_last_lap_without_a_duration_has_no_position():
    laps = [timed_lap(1, "2024-01-01T14:00:00+00:00", None)]

    assert position_at_lap_ends(laps, [change("2024-01-01T13:55:00+00:00", 5)]) == {1: None}


def test_lap_without_a_start_falls_back_to_none_when_last():
    laps = [timed_lap(1, None, 90.0)]

    assert position_at_lap_ends(laps, [change("2024-01-01T13:55:00+00:00", 5)]) == {1: None}


def test_next_lap_without_a_start_uses_this_laps_duration():
    laps = [timed_lap(1, "2024-01-01T14:00:00+00:00", 90.0), timed_lap(2, None, None)]
    changes = [change("2024-01-01T13:55:00+00:00", 5), change("2024-01-01T14:01:00+00:00", 4)]

    assert position_at_lap_ends(laps, changes)[1] == 4


def test_no_position_before_the_first_change():
    laps = [timed_lap(1, "2024-01-01T14:00:00+00:00"), timed_lap(2, "2024-01-01T14:01:30+00:00")]
    changes = [change("2024-01-01T14:02:00+00:00", 7)]

    assert position_at_lap_ends(laps, changes) == {1: None, 2: 7}


def test_no_changes_at_all_gives_no_positions():
    laps = [timed_lap(1, "2024-01-01T14:00:00+00:00")]

    assert position_at_lap_ends(laps, []) == {1: None}
