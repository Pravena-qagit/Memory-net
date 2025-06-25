import pytest
import pandas as pd
import ast

REQUIRED_COLUMNS = ["server_description", "dimm_ranks", "server_dimm_ranks"]

# Load your DataFrame here
df = pd.read_csv("08012025_cisco_db_import.csv")
df = df.dropna(subset=REQUIRED_COLUMNS)

# Parse stringified lists safely
df["server_dimm_ranks"] = df["server_dimm_ranks"].apply(
    lambda x: ast.literal_eval(x) if isinstance(x, str) else x
)   


# Test 1: Check for invalid data type (should be list)
def test_server_dimm_ranks_data_type():
    invalid_rows = df[~df["server_dimm_ranks"].apply(lambda x: isinstance(x, list))]
    assert invalid_rows.empty, f"{len(invalid_rows)} rows have invalid type for 'server_dimm_ranks'."


# Test 2 : Detect and sort exact duplicate rows (across all columns)
def test_sorted_duplicate_rows():
    # Convert server_dimm_ranks (list) to tuple so it can be compared
    temp_df = df.copy()
    temp_df["server_dimm_ranks"] = temp_df["server_dimm_ranks"].apply(
        lambda x: tuple(sorted(x)) if isinstance(x, list) else x
    )

    # Sort the DataFrame for easier debugging/reporting
    sorted_df = temp_df.sort_values(by=["server_description", "dimm_ranks", "server_dimm_ranks"])

    # Find duplicates based on all three columns
    duplicates = sorted_df[
        sorted_df.duplicated(subset=["server_description", "dimm_ranks", "server_dimm_ranks"], keep=False)
    ]

    # Export if duplicates are found
    if not duplicates.empty:
        duplicates.to_csv("sorted_duplicates.csv", index=False)

    assert duplicates.empty, (
        f"{len(duplicates)} duplicate rows found. See 'sorted_duplicates.csv' for details."
    )

# Test 3: Detect and sort exact mismatch rows (where dimm_ranks is not in server_dimm_ranks)
def test_sorted_dimm_ranks_mismatches():
    mismatch_rows = []

    for idx, row in df.iterrows():
        actual_rank = str(row["dimm_ranks"]).strip()
        list_values = [str(val).strip() for val in row["server_dimm_ranks"]]

        if actual_rank not in list_values:
            mismatch_rows.append(row)

    if mismatch_rows:
        # Create a new DataFrame for mismatches
        mismatch_df = pd.DataFrame(mismatch_rows)

        # Sort by key columns for readability
        mismatch_df = mismatch_df.sort_values(by=["server_description", "dimm_ranks"])

        # Save to CSV for manual review
        mismatch_df.to_csv("sorted_dimm_mismatches.csv", index=False)

    assert not mismatch_rows, (
        f"{len(mismatch_rows)} mismatched rows found. See 'sorted_dimm_mismatches.csv' for details."
    )
   