import pytest
import pandas as pd
from memory_extractor import (
    word_to_number,
    word_slot_extractor,
    simplify_memory_capacity,
    check_dimm_slot_match,
    check_memory_size_match,
    extract_chipset
)
# Test 1: word to number
@pytest.mark.parametrize("input_text, expected", [
    ("eight", "8"),
    ("twenty", "20"),
    ("thirty-two", "32"),
    ("zero", None),
    ("eleven", "11"),
    ("twenty one", "21"),
])
def test_word_to_number(input_text, expected):
    assert word_to_number(input_text) == expected

# Test 2: word slot extractor
@pytest.mark.parametrize("input_text, expected", [
    ("Supports 8 DIMM slots", "8"),
    ("Up to sixteen DIMM sockets", "16"),
    ("Contains four DIMM slots", "4"),
    ("In 12 DIMMs", "12"),
    ("8x DIMM sockets available", "8"),
    ("Up to 32 DIMM slots", "32"),
])
def test_word_slot_extractor(input_text, expected):
    assert word_slot_extractor(input_text) == expected

# Test 3: simplify_memory_capacity
@pytest.mark.parametrize("input_text, expected", [
    ("16 slots", "16"),
    ("  32  ", "32"),
    ("twenty", "20"),
    (None, None),
    ("", None),
])
def test_simplify_memory_capacity(input_text, expected):
    result = simplify_memory_capacity(input_text)
    assert result == expected or (pd.isna(result) and pd.isna(expected))

# Test 4: check_dimm_slot_match

def test_check_dimm_slot_match():
    # Match case
    row = pd.Series({
        "server_specification": '{"System Memory": {"Memory": {"Slot Count": "16"}}}',
        "dimm_slots": "16",
        "Memory Capacity": "16"
    })
    assert check_dimm_slot_match(row) == "match"

    # Mismatch case
    row["Memory Capacity"] = "12"
    assert check_dimm_slot_match(row) == "mismatch"

    # Missing values
    row["dimm_slots"] = None
    assert check_dimm_slot_match(row) == "Datas are not available"

    # Empty spec
    row = pd.Series({
        "server_specification": "{}",
        "dimm_slots": "16",
        "Memory Capacity": "16"
    })
    assert check_dimm_slot_match(row) == "Datas are not available"

# Test 5: check_memory_size_match

def test_check_memory_size_match():
    # Match case
    row = pd.Series({
        "server_specification": '{"System Memory": {"Memory": {"Items": ["Up to 512GB"]}}}',
        "maximum_memory": "512GB",
        "DIMM Sizes": "512GB"
    })
    assert check_memory_size_match(row) == "match"

    # Mismatch case
    row["DIMM Sizes"] = "256GB"
    assert check_memory_size_match(row) == "mismatch"

    # Missing
    row["maximum_memory"] = None
    assert check_memory_size_match(row) == "Datas are not available"

    # Empty spec
    row = pd.Series({
        "server_specification": "{}",
        "maximum_memory": "512GB",
        "DIMM Sizes": "512GB"
    })
    assert check_memory_size_match(row) == "Datas are not available"

 # Test 6: extract_chipset
@pytest.mark.parametrize("spec_json, expected", [
    ('{"chipset": "Intel C621"}', "Intel C621"),
    ('{"System": {"chipset": "Intel C622"}}', "Intel C622"),
    ('{"Board": {"Info": {"chipset": "AMD SP3"}}}', "AMD SP3"),  # Too deeply nested
    ('{"Processor": {"chipset": "Intel C600"}}', "Intel C600"),
    ('{"Components": [{"chipset": "Intel X299"}]}', "Intel X299"),
    ('{"Components": [{"name": "CPU"}, {"chipset": "Intel Z490"}]}', "Intel Z490"),
    ('{"SomeKey": "SomeValue"}', None),
    ('{}', None),
    ('Invalid JSON', None),  # Should not raise, just return None
])
def test_extract_chipset(spec_json, expected):
    result = extract_chipset(spec_json)
    assert result == expected
   
