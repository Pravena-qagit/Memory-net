import pytest
import pandas as pd
import json
import re
import atexit

# -------------------------------------------------
# Input CSV
# -------------------------------------------------
input_csv = "update_asrock_dimm_ranks.csv"

full_output_rows = []

# Track duplicates (store first occurrence row index)
seen_records = {}


# -------------------------------------------------
# Normalize function (Robust & Safe)
# -------------------------------------------------
def normalize_text(text):
    if pd.isna(text) or text is None:
        return None

    text = str(text).strip()

    if text == "":
        return None

    try:
        text = text.encode("utf-8").decode("unicode_escape")
    except Exception:
        pass

    text = text.replace("\u00a0", " ")
    text = re.sub(r"^-+\s*", "", text)
    text = re.sub(r"[^A-Za-z0-9 ]+", "", text)
    text = re.sub(r"\s+", " ", text)

    text = text.strip().upper()

    if text == "" or text == "NAN":
        return None

    return text


# -------------------------------------------------
# Recursive search for "Chipset" anywhere in JSON
# -------------------------------------------------
def find_chipset_recursive(data):
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() == "chipset":
                return value
            result = find_chipset_recursive(value)
            if result:
                return result

    elif isinstance(data, list):
        for item in data:
            result = find_chipset_recursive(item)
            if result:
                return result

    return None


# -------------------------------------------------
# Extract Chipset (Handles ALL structures)
# -------------------------------------------------
def extract_chipset(spec_text):
    if pd.isna(spec_text) or spec_text is None:
        return None

    text = str(spec_text)

    try:
        cleaned = text.replace("'", '"')
        parsed = json.loads(cleaned)

        # Try structured extraction
        chipset = find_chipset_recursive(parsed)
        if chipset:
            return chipset

    except Exception:
        pass

    # Regex fallback
    match = re.search(r'"Chipset"\s*:\s*"([^"]+)"', text)
    if match:
        return match.group(1)

    return None


# -------------------------------------------------
# Load CSV
# -------------------------------------------------
df = pd.read_csv(input_csv)

test_cases = [
    (
        idx,
        row.get("server_description"),
        row.get("server_specification"),
        row.get("chipset"),
    )
    for idx, row in df.iterrows()
]


# -------------------------------------------------
# Pytest Parametrized Test
# -------------------------------------------------
@pytest.mark.parametrize(
    "row_idx, server_description, server_specification, chipset",
    test_cases
)
def test_chipset_validation(
    row_idx, server_description, server_specification, chipset
):

    extracted_raw = extract_chipset(server_specification)

    extracted = normalize_text(extracted_raw)
    expected = normalize_text(chipset)
    description_norm = normalize_text(server_description)

    # -------------------------------------------------
    # Duplicate Detection Key
    # -------------------------------------------------
    duplicate_key = (description_norm, expected)

    if duplicate_key in seen_records:
        first_seen_row = seen_records[duplicate_key]
        result = f"DUPLICATE (same as row {first_seen_row})"

    else:
        seen_records[duplicate_key] = row_idx

        # -------------------------------------------------
        # Validation Logic
        # -------------------------------------------------
        if expected is None and extracted is None:
            result = "EMPTY"

        elif expected is not None and extracted is None:
            result = "MISSING"

        elif expected is None and extracted is not None:
            result = "MISMATCH"

        elif extracted != expected:
            result = "MISMATCH"

        else:
            result = "MATCH"

    row_data = {
        "Row": row_idx,
        "Server Description": server_description,
        "server_specification": server_specification,
        "Chipset Column": chipset,
        "Extracted Chipset From Spec": extracted_raw,
        "Normalized Extracted": extracted,
        "Normalized Expected": expected,
        "Result": result
    }

    full_output_rows.append(row_data)

    # Optional strict validation
    # assert result == "MATCH", result


# -------------------------------------------------
# Save ONE FULL OUTPUT CSV
# -------------------------------------------------
@atexit.register
def save_full_report():

    output_file = "chipset_validation_full_report.csv"

    pd.DataFrame(full_output_rows).to_csv(output_file, index=False)

    print(f"\nFull chipset validation report saved to: {output_file}")