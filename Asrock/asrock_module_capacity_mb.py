import pandas as pd
import re

input_csv = "asrock_db_import.csv"
output_csv = "module_capacity_mb_report.csv"

df = pd.read_csv(input_csv)

def convert_capacity_to_mb(capacity):
    if pd.isna(capacity):
        return None

    capacity = str(capacity).strip().upper()

    match = re.match(r"^(\d+)\s*(GB|TB)$", capacity)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "GB":
        return value * 1024

    if unit == "TB":
        return value * 1024 * 1024

    return None


results = []

for index, row in df.iterrows():
    capacity = row.get("capacity")
    actual_module_capacity_mb = row.get("module_capacity_mb")
    expected_module_capacity_mb = convert_capacity_to_mb(capacity)

    if pd.isna(actual_module_capacity_mb) or str(actual_module_capacity_mb).strip() == "":
        status = "Issue"
        issue_reason = "module_capacity_mb missing"
        actual_mb = ""

    else:
        try:
            actual_mb = int(float(actual_module_capacity_mb))
        except:
            actual_mb = None

        if expected_module_capacity_mb == actual_mb:
            status = "Verified"
            issue_reason = ""
        else:
            status = "Issue"
            issue_reason = "module_capacity_mb mismatch"

    results.append({
        "Row Index": index,
        "capacity": capacity,
        "Expected module_capacity_mb": expected_module_capacity_mb,
        "Actual module_capacity_mb": actual_mb,
        "Status": status,
        "Issue Reason": issue_reason
    })

pd.DataFrame(results).to_csv(output_csv, index=False)

print(f"Validation report saved to: {output_csv}")