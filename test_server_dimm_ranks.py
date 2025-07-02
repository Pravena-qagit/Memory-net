import pytest
import pandas as pd
import ast

input_csv = "08012025_cisco_db_import (2).csv"
# This file contains the test cases for validating DIMM ranks in server configuration.
def normalize(item):
    return item.strip().upper()

def parse_server_dimm_ranks(s):
    if pd.isna(s):
        return []
    try:
        parsed = ast.literal_eval(s)
    except Exception:
        parsed = s.strip("[]").split(",")
    return [normalize(x) for x in parsed if x.strip()]

def collect_dimm_ranks_for_server(sub_df):
    return [normalize(val) for val in sub_df["dimm_ranks"] if pd.notna(val)]

# Load and preparing the test cases 
df = pd.read_csv(input_csv)
test_cases = []

for server_description, sub_df in df.groupby("server_description"):
    expected_ranks = collect_dimm_ranks_for_server(sub_df)
    for idx, row in sub_df.iterrows():
        test_cases.append((
            server_description,  
            idx,                 
            expected_ranks,
            row["store_name"],
            row["option_part_no"],
            row["category"],
            row["ranks"],
            row["rank_width"],
            row["product_id"],
            row["dimm_ranks"],
            row["server_dimm_ranks"]
        ))

# Parametrize tests 
@pytest.mark.parametrize(
    "server_description, row_idx, expected_ranks, store_name, option_part_no, category, ranks, rank_width, product_id, dimm_ranks, server_dimm_ranks",
    test_cases,
    ids=[f"{row[0]}-row{row[1]}" for row in test_cases]
)
def test_server_dimm_ranks_match_dimm_ranks(
    server_description, row_idx, expected_ranks,
    store_name, option_part_no, category, ranks,
    rank_width, product_id, dimm_ranks, server_dimm_ranks
):
    actual_ranks = parse_server_dimm_ranks(server_dimm_ranks)

    missing = sorted([r for r in expected_ranks if r not in actual_ranks])
    mismatch = sorted([r for r in actual_ranks if r not in expected_ranks])
    duplicates = sorted([r for r in set(actual_ranks) if actual_ranks.count(r) > 1])

    if missing or mismatch or duplicates:
        issue_reason = []
        if missing:
            issue_reason.append("Missing DIMM Ranks")
        if mismatch:
            issue_reason.append("Mismatch DIMM Ranks")
        if duplicates:
            issue_reason.append("Duplicate DIMM Ranks")
        reason_text = ", ".join(issue_reason)

        print(f"\nServer: {server_description}")
        print(f"Row Index: {row_idx}")
        print(f"→ Reason: {reason_text}")
        print(f"Expected: {', '.join(expected_ranks)}")
        print(f"Actual:   {', '.join(actual_ranks)}")
        print(f"Missing:  {', '.join(missing)}")
        print(f"Mismatch: {', '.join(mismatch)}")
        print(f"Duplicates: {', '.join(duplicates)}\n")

        
        assert False, reason_text
    else:
        assert True 