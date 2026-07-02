import pytest
import pandas as pd
import ast
import atexit

input_csv = "supermicro_chunk2.csv"
# List to collect rows with issues
issue_rows = []
def normalize(item):
    """Normalize rank string"""
    return item.strip().upper()

def parse_server_dimm_ranks(s):
    """Parse server_dimm_ranks safely"""
    if pd.isna(s):
        return []
    try:
        parsed = ast.literal_eval(s)
    except Exception:
        parsed = s.strip("[]").split(",")
    return [normalize(x) for x in parsed if x.strip()]

def generate_dimm_ranks_from_ranks_and_width(ranks, rank_width):
    """Generate dimm_ranks from ranks and rank_width columns"""
    if pd.isna(ranks) or pd.isna(rank_width):
        return ""
    
    try:
        ranks_val = int(ranks)
        width_val = int(rank_width)
        return f"{ranks_val}Rx{width_val}"
    except (ValueError, TypeError):
        return ""

def collect_dimm_ranks_for_server(sub_df):
    """Get expected dimm ranks from subset"""
    return [normalize(val) for val in sub_df["dimm_ranks"] if pd.notna(val)]

# Load CSV and build test cases
df = pd.read_csv(input_csv)
test_cases = []

for server_description, sub_df in df.groupby("server_description"):
    expected_ranks = collect_dimm_ranks_for_server(sub_df)
    for idx, row in sub_df.iterrows():
        test_cases.append((
            server_description,
            idx,
            expected_ranks,
            row["dimm_ranks"],
            row["server_dimm_ranks"],
            row.get("ranks", ""),
            row.get("rank_width", "")
        ))

# Parametrize with pytest
@pytest.mark.parametrize(
    "server_description, row_idx, expected_ranks, dimm_ranks, server_dimm_ranks, ranks, rank_width",
    test_cases,
    ids=[f"{row[0]}-row{row[1]}" for row in test_cases]
)
def test_combined_ranks_and_width_generate_dimm_ranks(
    server_description, row_idx, expected_ranks, dimm_ranks, server_dimm_ranks, ranks, rank_width
):
    """Test that combining ranks and rank_width columns generates correct dimm_ranks"""
    
    # Generate dimm_ranks from ranks and rank_width
    generated_dimm_ranks = generate_dimm_ranks_from_ranks_and_width(ranks, rank_width)
    
    # Parse the actual dimm_ranks from the CSV
    actual_dimm_ranks = normalize(str(dimm_ranks)) if pd.notna(dimm_ranks) else ""
    
    # Check if generated matches actual (both should be normalized for comparison)
    if generated_dimm_ranks != actual_dimm_ranks:
        # Debug: Only show when there's actually a mismatch
        if generated_dimm_ranks and actual_dimm_ranks:
            print(f"DEBUG: Row {row_idx} - Generated: '{generated_dimm_ranks}' vs Actual: '{actual_dimm_ranks}'")
        
        issue_rows.append({
            "A": row.get("A", ""),
            "B": row.get("B", ""),
            "C": row.get("C", ""),
            "server_description": server_description,
            "processor": row.get("processor", ""),
            "module_capacity_mb": row.get("module_capacity_mb", ""),
            "ranks": ranks,
            "rank_width": rank_width,
            "generated_dimm_ranks": generated_dimm_ranks,
            "dimm_ranks": dimm_ranks,
            "server_dimm_ranks": server_dimm_ranks,
            "Missing": generated_dimm_ranks if generated_dimm_ranks else "",
            "Mismatch": actual_dimm_ranks if actual_dimm_ranks else "",
            "Duplicates": ""
        })
        
        assert False, f"Generated DIMM ranks '{generated_dimm_ranks}' doesn't match actual '{actual_dimm_ranks}'"
    else:
        assert True

# Additional test to validate server_dimm_ranks consistency
@pytest.mark.parametrize(
    "server_description, row_idx, expected_ranks, dimm_ranks, server_dimm_ranks, ranks, rank_width",
    test_cases,
    ids=[f"server-{row[0]}-row{row[1]}" for row in test_cases]
)
def test_server_dimm_ranks_match_dimm_ranks(
    server_description, row_idx, expected_ranks, dimm_ranks, server_dimm_ranks, ranks, rank_width
):
    """Test that server_dimm_ranks matches the expected dimm_ranks for the server"""
    
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
        
        issue_rows.append({
            "A": row.get("A", ""),
            "B": row.get("B", ""),
            "C": row.get("C", ""),
            "server_description": server_description,
            "processor": row.get("processor", ""),
            "module_capacity_mb": row.get("module_capacity_mb", ""),
            "ranks": ranks,
            "rank_width": rank_width,
            "dimm_ranks": dimm_ranks,
            "server_dimm_ranks": server_dimm_ranks,
            "Missing": ", ".join(missing) if missing else "",
            "Mismatch": ", ".join(mismatch) if mismatch else "",
            "Duplicates": ", ".join(duplicates) if duplicates else ""
        })
        
        assert False, reason_text
    else:
        assert True
# Save issues report after all tests
@atexit.register
def save_issues_to_csv():
    if issue_rows:
        output_file = "supermicro_dimm_rank_combined_issues.csv"
        column_order = [
            "A", "B", "C", "server_description", "processor", "module_capacity_mb", 
            "ranks", "rank_width", "generated_dimm_ranks",
            "dimm_ranks", "server_dimm_ranks", "Missing", "Mismatch", "Duplicates"
        ]
        pd.DataFrame(issue_rows)[column_order].to_csv(output_file, index=False)
        print(f"\nIssues saved to: {output_file}")
    else:
        print("\nNo DIMM rank issues found.")
