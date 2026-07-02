import pandas as pd
import re

# =====================================================
# 1️⃣ Load files
# =====================================================
print("Loading files...")
cisco_df = pd.read_csv("cisco_db_import.csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)

# =====================================================
# 2️⃣ Model normalization helper
# =====================================================
def normalize_model(model):
    if pd.isna(model):
        return None

    model = str(model).upper().strip()

    # Normalize E5-2600 v3 → E5-2600V3
    model = re.sub(r"\s+V", "V", model)

    # Remove spaces
    model = model.replace(" ", "")

    # Remove trailing junk ONLY (+, =)
    model = re.sub(r"[+=]+$", "", model)

    return model

# =====================================================
# 3️⃣ Prepare Intel lookup (NORMALIZED)
# =====================================================
intel_df["model_number_norm"] = intel_df["model_number"].apply(normalize_model)

intel_lookup = {
    row["model_number_norm"]: (row["product_family"], row["product_line"])
    for _, row in intel_df.iterrows()
}

intel_model_set = set(intel_lookup.keys())
print(f"Intel models loaded: {len(intel_model_set)}")

# =====================================================
# 4️⃣ Extract FULL model numbers from Cisco processor column
# =====================================================
def extract_all_models(text):
    if pd.isna(text):
        return []

    text = str(text)

    # Supports:
    # - E5-2600 v3
    # - E5-2699 v4
    # - 8562Y+=
    # - 8592V+
    raw_models = re.findall(
        r"\b(?:E\d-\d{4}\s*v\d|\d{4}[A-Z0-9]*[+=]?)\b",
        text,
        flags=re.IGNORECASE
    )

    cleaned_models = []
    for m in raw_models:
        m = normalize_model(m)
        if m:
            cleaned_models.append(m)

    return list(set(cleaned_models))  # remove duplicates

cisco_df["extracted_model_numbers"] = cisco_df["processor"].apply(extract_all_models)

# =====================================================
# 5️⃣ Cisco ↔ Intel Matching (COUNT-BASED)
# =====================================================
def match_cisco_row(model_list):
    if not model_list:
        return [], [], [], 0

    matched_families = set()
    matched_lines = set()
    missing_models = []
    matched_count = 0

    for model in model_list:
        if model in intel_model_set:
            family, line = intel_lookup[model]
            matched_families.add(family)
            matched_lines.add(line)
            matched_count += 1
        else:
            missing_models.append(model)

    return (
        list(matched_families),
        list(matched_lines),
        missing_models,
        matched_count
    )

(
    cisco_df["mapped_product_family"],
    cisco_df["mapped_product_line"],
    cisco_df["missing_model_numbers"],
    cisco_df["matched_model_count"]
) = zip(*cisco_df["extracted_model_numbers"].apply(match_cisco_row))

# =====================================================
# 6️⃣ STATUS LOGIC
# =====================================================
def get_intel_status(row):
    total = len(row["extracted_model_numbers"])
    matched = row["matched_model_count"]

    if total == 0:
        return "missing"
    if matched == 0:
        return "Family is not found"
    if matched < total:
        return f"{total - matched} of {total} processors missing"
    return "match"

cisco_df["status"] = cisco_df.apply(get_intel_status, axis=1)

# =====================================================
# 7️⃣ Save output
# =====================================================
output_file = "cisco_reintel_matched_output.csv"
cisco_df.to_csv(output_file, index=False)
print(f"✅ Saved {output_file}")
