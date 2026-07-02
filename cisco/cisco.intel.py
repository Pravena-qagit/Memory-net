import pandas as pd
import re

# -------------------------------------------------
# 1️⃣ Load files
# -------------------------------------------------
print("Loading files...")

cisco_df = pd.read_csv("final_output (5).csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)

# -------------------------------------------------
# 2️⃣ Prepare Intel lookup (MODEL ONLY)
# -------------------------------------------------
intel_df["model_number"] = intel_df["model_number"].astype(str).str.strip()

intel_lookup = {
    row["model_number"]: (row["product_family"], row["product_line"])
    for _, row in intel_df.iterrows()
}
intel_model_set = set(intel_lookup.keys())
# -------------------------------------------------
# 3️⃣ Extract FULL model numbers from Cisco processor cell
# -------------------------------------------------
def extract_all_models(text):
    if pd.isna(text):
        return []
    text = str(text)
    return re.findall(r'\b[A-Za-z0-9\-]+(?:P|X)?\b', text)
cisco_df["extracted_model_numbers"] = cisco_df["processor"].apply(extract_all_models)
# -------------------------------------------------
# 4️⃣ Cisco ↔ Intel Matching (COUNT-BASED)
# -------------------------------------------------
def match_cisco_row(model_list):
    if not model_list:
        return [], [], [] 

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

# -------------------------------------------------
# 5️⃣ STATUS LOGIC (YOUR REQUESTED LOGIC)
# -------------------------------------------------
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

# -------------------------------------------------
# 6️⃣ Save output
# -------------------------------------------------
cisco_df.to_csv("cisco_intel_matched_output.csv", index=False)
print("✅ Saved cisco_intel_matched_output.csv")
