import pandas as pd

# ---------------- helper ----------------
def normalize(text):
    """Normalize text for comparison (case + spaces)"""
    return " ".join(text.lower().split())

# ---------------- load CSV ----------------
df = pd.read_csv("24012026_dell_db_import.csv")

results = []

# ---------------- process rows ----------------
for _, row in df.iterrows():
    server_desc = str(row["server_description"]).strip()

    expected_B = ""
    expected_C = ""

    parts = server_desc.split()

    # ==================================================
    # CASE 0: Empty or single word
    # ==================================================
    if len(parts) <= 1:
        expected_B = server_desc
        expected_C = ""

    # ==================================================
    # CASE 1: Latitude Chromebook with screen size + model
    # Example: Latitude Chromebook 14 5430
    # ==================================================
    elif (
        len(parts) >= 4
        and parts[0].isalpha()
        and parts[1].isalpha()
        and parts[2].isdigit()
        and parts[3].isdigit()
        and len(parts[3]) == 4
    ):
        expected_B = " ".join(parts[:3])
        expected_C = parts[3]

    # ==================================================
    # CASE 2: Second word is 4-digit model
    # Example: Latitude 7420
    # ==================================================
    elif len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) == 4:
        expected_B = parts[0]
        expected_C = " ".join(parts[1:])

    # ==================================================
    # CASE 3: Second word numeric (non-4-digit)
    # Example: Inspiron 15 3000
    # ==================================================
    elif len(parts) >= 3 and parts[1].isdigit():
        expected_B = f"{parts[0]} {parts[1]}"
        expected_C = " ".join(parts[2:])

    # ==================================================
    # CASE 4: Brand + series containing digits
    # Example:
    # Alienware m15 R7 (AMD)
    # Alienware m18 R1 (AMD)
    # ==================================================
    elif (
        len(parts) >= 3
        and parts[0].isalpha()
        and any(char.isdigit() for char in parts[1])
    ):
        expected_B = parts[0]
        expected_C = " ".join(parts[1:])

    # ==================================================
    # CASE 5: First two words start with same letter
    # Example: Alienware Aurora R13 / R15
    # ==================================================
    elif (
        len(parts) >= 3
        and parts[0][0].lower() == parts[1][0].lower()
        and any(char.isdigit() for char in parts[2])
    ):
        expected_B = parts[0]
        expected_C = " ".join(parts[1:])

    # ==================================================
    # CASE 6: Two-word family + model
    # Example:
    # Precision Workstation 3240
    # Precision Workstation R3930
    # ==================================================
    elif (
        len(parts) >= 3
        and parts[0].isalpha()
        and parts[1].isalpha()
        and any(char.isdigit() for char in parts[2])
    ):
        expected_B = f"{parts[0]} {parts[1]}"
        expected_C = " ".join(parts[2:])

    # ==================================================
    # CASE 7: Parentheses metadata ONLY (non-model)
    # Example: PowerEdge R740 (2U)
    # ==================================================
    elif (
        "(" in server_desc
        and not (
            len(parts) >= 2
            and any(char.isdigit() for char in parts[1])
        )
    ):
        expected_B = server_desc.split("(")[0].strip()
        expected_C = "(" + server_desc.split("(", 1)[1].strip()

    # ==================================================
    # CASE 8: Fallback
    # ==================================================
    else:
        expected_B = parts[0]
        expected_C = " ".join(parts[1:])

    # ---------------- actual values ----------------
    actual_B = "" if pd.isna(row["B"]) else str(row["B"]).strip()
    actual_C = "" if pd.isna(row["C"]) else str(row["C"]).strip()

    # ---------------- status ----------------
    if not actual_B or not actual_C:
        status = "MISSING"
    elif (
        normalize(actual_B) != normalize(expected_B)
        or normalize(actual_C) != normalize(expected_C)
    ):
        status = "MISMATCH"
    else:
        status = "MATCH"

    # ---------------- collect ----------------
    results.append({
        "server_description": server_desc,
        "actual_B": actual_B,
        "expected_B": expected_B,
        "actual_C": actual_C,
        "expected_C": expected_C,
        "status": status
    })

# ---------------- output ----------------
result_df = pd.DataFrame(results)
result_df.to_csv("dell_normalization_report.csv", index=False)

print(result_df["status"].value_counts())
