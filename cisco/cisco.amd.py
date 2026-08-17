import pandas as pd
import re
import ast

# 1️⃣ Load files
print("Loading files...")

cisco_df = pd.read_csv("cisco_db_import.csv", low_memory=False)
amd_df = pd.read_csv("amd_processor_import_db (3).csv", low_memory=False)

# 2️⃣ Prepare AMD lookup (EPYC ONLY)
def extract_amd_model(product_name):
    """
    Extract ONLY EPYC-style AMD models.
    Ignore A-series, Ryzen, Threadripper, etc.
    """
    if pd.isna(product_name):
        return None
    text = str(product_name)
    #  Ignore hyphenated A-series models like A6-8570
    if re.search(r'\b[A-Z]\d-\d+\b', text):
        return None
    #  Match EPYC-style models: 9845, 9654P, 9684X
    match = re.search(r'\b(\d{4,5}[PX]?)\b', text)
    return match.group(1) if match else None

amd_df["amd_model"] = amd_df["product_name"].apply(extract_amd_model)

amd_lookup = {
    row["amd_model"]: row["product_family"]
    for _, row in amd_df.iterrows()
    if pd.notna(row["amd_model"])
}
amd_model_set = set(amd_lookup.keys())

# 3️⃣ Extract & clean Cisco processor column
def extract_and_clean_cisco_models(text):
    """
    RULES:
    - Handle stringified lists
    - Keep Intel strings untouched
    - Remove ONLY leading 'A' from AMD EPYC models
    """
    if pd.isna(text):
        return []

    # Handle stringified lists
    if isinstance(text, str) and text.strip().startswith("[") and text.strip().endswith("]"):
        try:
            tokens = ast.literal_eval(text)
        except Exception:
            tokens = [text]
    else:
        tokens = re.split(r'[,\n;/]+', str(text))
    cleaned = []

    for token in tokens:
        token = str(token).strip()

        # Remove leading A only for EPYC-style models
        if re.fullmatch(r'A\d{4,5}[PX]?', token):
            cleaned.append(token[1:])
        else:
            cleaned.append(token)
    return cleaned

cisco_df["extracted_model_numbers"] = cisco_df["processor"].apply(
    extract_and_clean_cisco_models
)

# 4️⃣ Cisco ↔ AMD Matching Logic
def match_cisco_amd_row(model_list):
    if not model_list:
        return [], [], 0

    matched_families = set()
    missing_models = []
    matched_count = 0

    for model in model_list:
        # Only EPYC-style models participate
        if re.fullmatch(r'\d{4,5}[PX]?', model):
            if model in amd_model_set:
                matched_families.add(amd_lookup[model])
                matched_count += 1
            else:
                missing_models.append(model)

    return list(matched_families), missing_models, matched_count
(
    cisco_df["mapped_amd_product_family"],
    cisco_df["missing_amd_model_numbers"],
    cisco_df["matched_model_count"]
) = zip(*cisco_df["extracted_model_numbers"].apply(match_cisco_amd_row))

# 5️⃣ Status logic (YOUR RULE)
def get_amd_status(row):
    total = sum(
        1 for x in row["extracted_model_numbers"]
        if re.fullmatch(r'\d{4,5}[PX]?', x)
    )
    matched = row["matched_model_count"]
    if total == 0:
        return "missing"
    if matched == 0:
        return "Family is not found"
    if matched < total:
        return f"{total - matched} of {total} processors missing"
    return "match"
cisco_df["amd_status"] = cisco_df.apply(get_amd_status, axis=1)

# 6️⃣ Save output
cisco_df.to_csv("cisco_amd_matched_output.csv", index=False)
print("Saved cisco_amd_matched_output.csv")
