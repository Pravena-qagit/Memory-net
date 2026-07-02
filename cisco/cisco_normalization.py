import pandas as pd
# Load CSV
df = pd.read_csv("12012026_cisco_db_import.csv")
results = []
for _, row in df.iterrows():
    server_desc = str(row["server_description"]).strip()

    parts = server_desc.split()
    expected_A = parts[0] if len(parts) >= 1 else ""
    expected_B = parts[1] if len(parts) >= 2 else ""
    expected_C = " ".join(parts[2:]) if len(parts) >= 3 else ""

    actual_A = "" if pd.isna(row["A"]) else str(row["A"]).strip()
    actual_B = "" if pd.isna(row["B"]) else str(row["B"]).strip()
    actual_C = "" if pd.isna(row["C"]) else str(row["C"]).strip()
# status determination
    if not actual_A or not actual_B or not actual_C:
        status = "MISSING"
    elif (
        actual_A != expected_A
        or actual_B != expected_B
        or actual_C != expected_C
    ):
        status = "MISMATCH"
    else:
        status = "MATCH"

    results.append({
        "server_description": server_desc,
        "expected_A": expected_A,
        "actual_A": actual_A,
        "expected_B": expected_B,
        "actual_B": actual_B,
        "expected_C": expected_C,
        "actual_C": actual_C,
        "status": status
    })
# Create report
result_df = pd.DataFrame(results)
# Save report
result_df.to_csv("normalization_report.csv", index=False)
print(result_df["status"].value_counts())
