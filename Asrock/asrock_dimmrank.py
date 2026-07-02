import pytest
import pandas as pd
import ast
import atexit
# load csv file
input_csv = "24042026_asrock_dimm_ranks.csv"
# Lists to collect issue and verified rows
issue_rows = []
verified_rows = []
# normalization function
def normalize(item):
    return item.strip().upper()
def parse_server_dimm_ranks(s):
    if pd.isna(s):
        return []
    try:
        parsed = ast.literal_eval(s)
        if not isinstance(parsed, list):
            parsed = [parsed]
    except Exception:
        parsed = s.strip("[]").split(",")
    return [normalize(x) for x in parsed if str(x).strip()]
def collect_dimm_ranks_for_server(sub_df):
    return [normalize(val) for val in sub_df["dimm_ranks"] if pd.notna(val)]
# Load the CSV data
df = pd.read_csv(input_csv)
test_cases = []

for server_description, sub_df in df.groupby("server_description"):
    expected_ranks = collect_dimm_ranks_for_server(sub_df)

    for idx, row in sub_df.iterrows():
        test_cases.append((
            server_description,
            idx,
            expected_ranks,
            row.get("store"),
            row.get("option_part_no"),
            row.get("category"),
            row.get("ranks"),
            row.get("rank_width"),
            row.get("product_id"),
            row.get("dimm_ranks"),
            row.get("server_dimm_ranks")
        ))

# -------------------------------------------------
# Pytest Parametrization
# -------------------------------------------------
@pytest.mark.parametrize(
    "server_description, row_idx, expected_ranks, store, option_part_no, category, ranks, rank_width, product_id, dimm_ranks, server_dimm_ranks",
    test_cases,
    ids=[f"{row[0]}-row{row[1]}" for row in test_cases]
)
def test_server_dimm_ranks_match_dimm_ranks(
    server_description, row_idx, expected_ranks,
    store, option_part_no, category, ranks,
    rank_width, product_id, dimm_ranks, server_dimm_ranks
):
    actual_ranks = parse_server_dimm_ranks(server_dimm_ranks)

    missing = sorted([r for r in expected_ranks if r not in actual_ranks])
    mismatch = sorted([r for r in actual_ranks if r not in expected_ranks])
    duplicates = sorted([r for r in set(actual_ranks) if actual_ranks.count(r) > 1])
# if there are any issues, log them
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
        issue_rows.append({
            "Store": store,
            "Option Part No": option_part_no,
            "Server Description": server_description,
            "Category": category,
            "Ranks": ranks,
            "Rank Width": rank_width,
            "Product ID": product_id,
            "dimm_ranks": dimm_ranks,
            "server_dimm_ranks": server_dimm_ranks,
            "Missing": ", ".join(missing),
            "Mismatch": ", ".join(mismatch),
            "Duplicates": ", ".join(duplicates)
        })

        assert False, reason_text

    # -------------------------------------------------
    # ✅ VERIFIED (NO ISSUE)
    # -------------------------------------------------
    else:
        verified_rows.append({
            "server_description": server_description,
            "A": store,
            "B": option_part_no,
            "C": category,
            "hosturl": product_id,
            "dimm_ranks": dimm_ranks,
            "server_dimm_ranks": server_dimm_ranks,
            "Missing": "",
            "Mismatch": "",
            "Duplicates": ""
        })

        assert True

# -------------------------------------------------
# Save CSV Reports After Pytest Execution
# -------------------------------------------------
@atexit.register
def save_reports():
    final_rows = []

    # Add issue rows
    for row in issue_rows:
        row["Status"] = "Issue"
        issue_reason = []

        if row.get("Missing"):
            issue_reason.append("Missing DIMM Ranks")
        if row.get("Mismatch"):
            issue_reason.append("Mismatch DIMM Ranks")
        if row.get("Duplicates"):
            issue_reason.append("Duplicate DIMM Ranks")

        row["Issue Reason"] = ", ".join(issue_reason)
        final_rows.append(row)

    # Add verified rows
    for row in verified_rows:
        final_rows.append({
            "Store": row.get("A"),
            "Option Part No": row.get("B"),
            "Server Description": row.get("server_description"),
            "Category": row.get("C"),
            "Ranks": "",
            "Rank Width": "",
            "Product ID": row.get("hosturl"),
            "dimm_ranks": row.get("dimm_ranks"),
            "server_dimm_ranks": row.get("server_dimm_ranks"),
            "Missing": "",
            "Mismatch": "",
            "Duplicates": "",
            "Status": "Verified",
            "Issue Reason": ""
        })

    if final_rows:
        final_file = "asrock_server_dimm_rank_final_report.csv"

        final_columns = [
            "Store",
            "Option Part No",
            "Server Description",
            "Category",
            "Ranks",
            "Rank Width",
            "Product ID",
            "dimm_ranks",
            "server_dimm_ranks",
            "Missing",
            "Mismatch",
            "Duplicates",
            "Status",
            "Issue Reason"
        ]

        pd.DataFrame(final_rows)[final_columns].to_csv(final_file, index=False)
        print(f"\n Final combined report saved to: {final_file}")
    else:
        print("\n No rows found to save.")
