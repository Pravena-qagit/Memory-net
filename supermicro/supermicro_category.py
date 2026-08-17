import pandas as pd
import ast

INPUT_FILE = "20042026_final_supermicro_db_import.csv"
OUTPUT_FILE = "category_report.csv"

# Required categories
REQUIRED_CATEGORIES = ["ssd", "hdd", "memory"]


def clean_value(value):
    """
    Clean normal string values.
    """
    if pd.isna(value):
        return ""
    return str(value).strip()


def extract_option_part_numbers(value):
    """
    Handles normal text and list-like values.

    Example:
    "ABC123" -> ["ABC123"]

    "['ABC123', 'XYZ456']" -> ["ABC123", "XYZ456"]
    """
    if pd.isna(value):
        return []

    value = str(value).strip()

    if value == "":
        return []

    # If value is stored like Python list string
    if value.startswith("[") and value.endswith("]"):
        try:
            parsed_value = ast.literal_eval(value)

            if isinstance(parsed_value, list):
                return [str(item).strip() for item in parsed_value if str(item).strip()]

        except Exception:
            pass

    # Normal single value
    return [value]


# Read CSV
df = pd.read_csv(INPUT_FILE)

# Clean column names
df.columns = df.columns.str.strip()

# Validate required columns
required_columns = ["server_description", "category", "option_part_no"]

missing_columns = [col for col in required_columns if col not in df.columns]

if missing_columns:
    raise Exception(f"Missing columns in CSV: {missing_columns}")

# Clean category
df["category_clean"] = df["category"].astype(str).str.strip().str.lower()

# Filter only required categories
filtered_df = df[df["category_clean"].isin(REQUIRED_CATEGORIES)]

final_rows = []

# Group by server_description and category
for (server_description, category), group in filtered_df.groupby(
    ["server_description", "category_clean"]
):
    unique_part_numbers = []

    for value in group["option_part_no"]:
        part_numbers = extract_option_part_numbers(value)

        for part_no in part_numbers:
            if part_no not in unique_part_numbers:
                unique_part_numbers.append(part_no)

    final_rows.append({
        "server_description": server_description,
        "option_part_no": group["option_part_no"].tolist(),
        "category": category,
        "option_part_no_without_duplicate": unique_part_numbers
    })

# Create output CSV
output_df = pd.DataFrame(final_rows)

output_df.to_csv(OUTPUT_FILE, index=False)

print("CSV filter completed successfully.")
print(f"Output file created: {OUTPUT_FILE}")