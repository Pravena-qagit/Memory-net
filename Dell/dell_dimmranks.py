import os
import csv
import ast
import pandas as pd
import pytest
import re
from pandas.errors import EmptyDataError

# 1) Point to the CSV once
CSV_PATH = os.path.join(os.path.dirname(__file__), "30092025dell_db_import1.csv")

@pytest.fixture(scope="session")
def df():
    """
    Load the CSV into a DataFrame once per session.
    Skip all tests if mismatch, empty, or parsing fails.
    """
    if not os.path.exists(CSV_PATH):
        pytest.skip(f"CSV not found at {CSV_PATH}")
    try:
        # First attempt with fast C engine
        data = pd.read_csv(CSV_PATH)
    except EmptyDataError:
        pytest.skip(f"No data found in CSV at {CSV_PATH}")
    except pd.errors.ParserError:
        # Retry with Python engine, skip bad rows
        try:
            data = pd.read_csv(CSV_PATH, engine="python", on_bad_lines="skip")
        except Exception as e:
            pytest.skip(f"CSV could not be parsed: {e}")
    except Exception as e:
        pytest.skip(f"Unexpected error reading CSV: {e}")

    data.columns = data.columns.str.strip()
    return data


# 2) Helper: parse a Python-literal or comma-sep list into flat list of combos
def _parse_list(cell: str) -> list[str]:
    text = str(cell).strip()
    if not text or text.lower() in ("nan", "[]"):
        return []
    try:
        parsed = ast.literal_eval(text)
    except Exception:
        # fallback: split on commas
        return [s.strip().strip("'\"") for s in text.split(",") if s.strip()]

    def _flatten(x):
        for item in x:
            if isinstance(item, (list, tuple)):
                yield from _flatten(item)
            else:
                yield str(item).strip().strip("'\"")
    return list(_flatten(parsed))

# Define the valid DIMM rank values
VALID_DIMM_RANKS = {
    "1Rx2", "1Rx4", "1Rx8", "1Rx16",
    "2Rx4", "2Rx8", "2Rx16",
    "3Rx4",
    "4Rx4", "4Rx8",
    "8Rx4"
}

def _validate_dimm_ranks(dimm_ranks_list: list[str]) -> tuple[list[str], list[str]]:
    """
    Validate DIMM ranks against the valid set.
    Returns (valid_ranks, invalid_ranks)
    """
    valid_ranks = []
    invalid_ranks = []
    for rank in dimm_ranks_list:
        if rank in VALID_DIMM_RANKS:
            valid_ranks.append(rank)
        else:
            invalid_ranks.append(rank)
    return valid_ranks, invalid_ranks

def convert_capacity_to_mb(capacity_str):
    """
    Convert capacity string (e.g., '32GB', '1TB') to MB as integer.
    """
    if not isinstance(capacity_str, str):
        return None
    capacity_str = capacity_str.strip().upper()
    match = re.match(r"([\d\.]+)\s*(TB|GB|MB)", capacity_str)
    if not match:
        return None
    value, unit = match.groups()
    value = float(value)
    if unit == "TB":
        return int(value * 1024 * 1024)
    elif unit == "GB":
        return int(value * 1024)
    elif unit == "MB":
        return int(value)
    return None

def test_capacity_mb_conversion_and_comparison(df: pd.DataFrame):
    """
    Converts 'capacity' column to MB, stores in 'capacity_mb_converted',
    and compares with 'module_capacity_mb'.
    Writes a report of mismatches.
    """
    assert "capacity" in df.columns, "Missing 'capacity' column"
    assert "module_capacity_mb" in df.columns, "Missing 'module_capacity_mb' column"

    df["capacity_mb_converted"] = df["capacity"].apply(convert_capacity_to_mb)
    mismatches = []
    for idx, row in df.iterrows():
        converted = row["capacity_mb_converted"]
        module_mb = row["module_capacity_mb"]
        if pd.isnull(converted) or pd.isnull(module_mb):
            continue
        if int(converted) != int(module_mb):
            mismatches.append({
                "row": idx,
                "capacity": row["capacity"],
                "capacity_mb_converted": converted,
                "module_capacity_mb": module_mb
            })
def test_dimm_ranks_presence_in_server(df: pd.DataFrame):
    """
    Validate dimm_ranks vs server_dimm_ranks for each row.
    Check for invalid values, duplicates, and include capacity checks.
    Writes results to dimm_ranks_qa_report.csv.
    """
    for col in ("dimm_ranks", "server_dimm_ranks", "server_description"):
        assert col in df.columns, f"Missing required column '{col}'"

    df["capacity_mb_converted"] = df["capacity"].apply(convert_capacity_to_mb) if "capacity" in df.columns else ""

    report = []
    extracted_server_ranks = []

    for idx, row in df.iterrows():
        dimm_list = _parse_list(row["dimm_ranks"])
        server_dimm_ranks = _parse_list(row["server_dimm_ranks"])
        server_desc = str(row["server_description"]).strip()

        valid_dimm_ranks, invalid_dimm_ranks = _validate_dimm_ranks(dimm_list)
        valid_server_ranks, invalid_server_ranks = _validate_dimm_ranks(server_dimm_ranks)

        dimm_set = set(valid_dimm_ranks)
        server_set = set(valid_server_ranks)

        status = "PASS"
        issues = []

        if invalid_dimm_ranks:
            status = "FAIL"
            issues.append(f"Invalid dimm_ranks: {', '.join(invalid_dimm_ranks)}")

        if invalid_server_ranks:
            status = "FAIL"
            issues.append(f"Invalid server_dimm_ranks: {', '.join(invalid_server_ranks)}")

        mismatch = dimm_set - server_set
        if mismatch:
            status = "FAIL"
            # You requested: no need to append dimm_ranks not in server_dimm_ranks

        duplicate_ranks = [item for item in server_dimm_ranks if server_dimm_ranks.count(item) > 1]
        if duplicate_ranks:
            status = "FAIL"
            issues.append(f"Duplicates in server_dimm_ranks: {', '.join(set(duplicate_ranks))}")

        dimm_rank_issue = ""
        server_dimm_rank_issue = ""
        capacity_issue = ""
        for issue in issues:
            if issue.startswith("Invalid dimm_ranks"):
                dimm_rank_issue += issue + "; "
            elif issue.startswith("Invalid server_dimm_ranks") or issue.startswith("Duplicates"):
                server_dimm_rank_issue += issue + "; "
            elif "capacity" in issue.lower():
                capacity_issue += issue + "; "

        dimm_rank_issue = dimm_rank_issue.strip("; ").replace(";;", ";")
        server_dimm_rank_issue = server_dimm_rank_issue.strip("; ").replace(";;", ";")
        capacity_issue = capacity_issue.strip("; ").replace(";;", ";")

        report.append({
            "row": idx,
            "A": row.get("A", ""),
            "B": row.get("B", ""),
            "C": row.get("C", ""),
            "ranks": row.get("ranks", ""),
            "rank_width": row.get("rank_width", ""),
            "server_description": server_desc,
            "dimm_ranks": ",".join(sorted(dimm_list)),
            "server_dimm_ranks": ",".join(sorted(server_dimm_ranks)),
            "capacity": row.get("capacity", ""),
            "capacity_mb_converted": row.get("capacity_mb_converted", ""),
            "module_capacity_mb": row.get("module_capacity_mb", ""),
            "extracted_dimm_ranks": ",".join(sorted(valid_dimm_ranks)) if valid_dimm_ranks else "",
            "extracted_server_dimm_ranks": ",".join(sorted(valid_server_ranks)) if valid_server_ranks else "",
            "extracted_module_capacity_mb": row.get("capacity_mb_converted", ""),
            "invalid_dimm_ranks": ",".join(sorted(invalid_dimm_ranks)) if invalid_dimm_ranks else "",
            "invalid_server_ranks": ",".join(sorted(invalid_server_ranks)) if invalid_server_ranks else "",
            "dimm_rank_issue": dimm_rank_issue,
            "server_dimm_rank_issue": server_dimm_rank_issue,
            "capacity_issue": capacity_issue,
            "status": status
        })

        extracted_server_ranks.append(",".join(sorted(valid_server_ranks)))

    # Create the three extracted columns
    df["extracted_dimm_ranks"] = [",".join(sorted(_parse_list(row["dimm_ranks"]))) for _, row in df.iterrows()]
    df["extracted_server_dimm_ranks"] = extracted_server_ranks
    df["extracted_module_capacity_mb"] = df["capacity"].apply(convert_capacity_to_mb) if "capacity" in df.columns else None

    # # Save the DataFrame with extracted columns to a separate CSV
    # extracted_df_path = os.path.join(os.path.dirname(__file__), "supermicro_dimm_ranks.csv")
    # df.to_csv(extracted_df_path, index=False)

    out_path = os.path.join(os.path.dirname(__file__), "dimm_ranks_dell_report.csv")
    with open(out_path, "w", newline="") as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=["row", "A", "B", "C", "ranks", "rank_width", "server_description", "dimm_ranks", "server_dimm_ranks",
                        "capacity", "capacity_mb_converted", "module_capacity_mb",
                        "extracted_dimm_ranks", "extracted_server_dimm_ranks", "extracted_module_capacity_mb",
                        "invalid_dimm_ranks", "invalid_server_ranks",
                        "dimm_rank_issue", "server_dimm_rank_issue", "capacity_issue", "status"]
        )
        writer.writeheader()
        writer.writerows(report)

    fails = [r for r in report if r["status"] == "FAIL"]
    if fails:
        pytest.fail(
            f"DIMM ranks validation failed in the following rows: {', '.join(str(r['row']) for r in fails)}\n"
            f"See 'dimm_ranks_dell_report.csv' for details."
        )
# end of file
