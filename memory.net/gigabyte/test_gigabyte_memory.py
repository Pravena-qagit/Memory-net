import pytest
import pandas as pd
from memory_extractor import (
    word_to_number,
    word_slot_extractor,
    simplify_memory_capacity,
    check_dimm_slot_match,
    check_memory_size_match
)
# Test 1: word to number
@pytest.mark.parametrize("input_text, expected", [
    ("eight", "8"),
    ("twenty", "20"),
    ("thirty-two", "32"),
    ("zero", None),
    ("eleven", "11"),
    ("twenty one", "21"),  # Test for two-word number
])
def test_word_to_number(input_text, expected):
    assert word_to_number(input_text) == expected

# Test 2: word slot extractor
@pytest.mark.parametrize("input_text, expected", [
    ("2 x DDR4 DIMM sockets supporting up to 32GB of system memory","2"),
    ("8 x DIMM slots", "8"),
])
def test_word_slot_extractor(input_text, expected):
    assert word_slot_extractor(input_text) == expected

# Test 3: simplify_memory_capacity
@pytest.mark.parametrize("input_text, expected", [
    ("16 x DIMM slots", "16"),
    ("  32  ", "32"),
    ("twenty", "20"),
    (None, None),
    ("", None),
])
def test_simplify_memory_capacity(input_text, expected):
    result = simplify_memory_capacity(input_text)
    assert result == expected or (pd.isna(result) and pd.isna(expected))

def test_check_dimm_slot_match():
    # Match case
    row = pd.Series({
        "server_specification":  {"Memory": ["16 x DIMM slots"]},
        "dimm_slots": "16",
        "Extracted Maximum Memory": "16"
    })
    assert check_dimm_slot_match(row) == "match"

    # Mismatch case
    row["Extracted Maximum Memory"] = "12"
    assert check_dimm_slot_match(row) == "mismatch"

    # Missing values
    row["dimm_slots"] = None
    assert check_dimm_slot_match(row) == "Datas are not available"

    # Empty spec
    row = pd.Series({
        "server_specification": "{}",
        "dimm_slots": "16",
        "Extracted Maximum Memory": "16"
    })
    assert check_dimm_slot_match(row) == "Datas are not available"

# Test 5: check_memory_size_match

def test_check_memory_size_match():
    # Match case
    row = pd.Series({
        "server_specification":  {"Memory": ["RDIMM modules up to 128GB supported"]},
        "maximum_memory": "128GB",
        "Extracted DIMM Sizes": "128GB"
    })
    assert check_memory_size_match(row) == "match"

    # Mismatch case
    row["Extracted DIMM Sizes"] = "256GB"
    assert check_memory_size_match(row) == "mismatch"

    # Missing
    row["maximum_memory"] = None
    assert check_memory_size_match(row) == "Datas are not available"

    # Empty spec
    row = pd.Series({
        "server_specification": "{}",
        "maximum_memory": "128GB",
        "Extracted DIMM Sizes": "128GB"
    })
    assert check_memory_size_match(row) == "Datas are not available"