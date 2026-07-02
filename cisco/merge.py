import pandas as pd
import re
import ast

# -------------------------------------------------
# 1️⃣ Load files
# -------------------------------------------------
print("Loading files...")

cisco_df = pd.read_csv("final_output (5).csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)
amd_df   = pd.read_csv("amd_processor_import_db (3).csv", low_memory=False)

# -------------------------------------------------
# 2️⃣ Prepare INTEL lookup
# -------------------------------------------------
intel_df["model_number"] = intel_df["model_number"].astype(str).str.strip()

intel_lookup = {
    row["model_number"]: row["product_family"]
    for _, row in intel_df.iterrows()
}

intel_model_set = set(intel_lookup.keys())

# -------------------------------------------------
# 3️⃣ Prepare AMD lookup (EPYC ONLY)
# -------------------------------------------------
def extract_amd_model(product_name):
    if pd.isna(product_name):
        return None

    text = str(product_name)

    # ❌ Ignore A-series like A6-8570
    if re.search(r'\bA\d-\d+\b', text):
        return None

    # ✅ EPYC models
    match = re.search(r'\b(\d{4,5}[PX]?)\b', text)
    return match.group(1) if match else None


amd_df["amd_model"] = amd_df["product_name"].apply(extract_amd_model)

amd_lookup = {
    row["amd_model"]: row["product_family"]
    for _, row in amd_df.iterrows()
    if pd.notna(row["amd_model"])
}

amd_model_set = set(amd_lookup.keys())

# -------------------------------------------------
# 4️⃣ Extract & clean Cisco processor column
# -------------------------------------------------
def extract_and_clean_cisco_models(text):
    if pd.isna(text):
        return []

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

        # Remove ONLY leading 'A'
        if token.startswith("A") and len(token) > 1 and token[1].isalnum():
            cleaned.append(token[1:])
        else:
            cleaned.append(token)

    return cleaned


cisco_df["extracted_models"] = cisco_df["processor"].apply(
    extract_and_clean_cisco_models
)

# -------------------------------------------------
# 5️⃣ Unified Intel + AMD matching
# -------------------------------------------------
def match_row(model_list):
    if not model_list:
        return [], [], "missing", "unknown"

    matched_families = set()
    missing_models = []
    matched_count = 0
    total = 0

    intel_found = False
    amd_found = False

    for model in model_list:

        # ---------- INTEL ----------
        if model in intel_model_set:
            matched_families.add(intel_lookup[model])
            matched_count += 1
            total += 1
            intel_found = True
            continue

        # ---------- AMD (EPYC only) ----------
        if re.fullmatch(r'\d{4,5}[PX]?', model):
            total += 1
            if model in amd_model_set:
                matched_families.add(amd_lookup[model])
                matched_count += 1
                amd_found = True
            else:
                missing_models.append(model)
            continue

    # ---------- STATUS ----------
    if total == 0:
        status = "missing"
    elif matched_count == 0:
        status = "Family is not found"
    elif matched_count < total:
        status = f"{total - matched_count} of {total} processors missing"
    else:
        status = "match"

    # ---------- VENDOR ----------
    if intel_found and amd_found:
        vendor = "both"
    elif intel_found:
        vendor = "intel"
    elif amd_found:
        vendor = "amd"
    else:
        vendor = "unknown"

    return (
        list(matched_families),
        missing_models,
        status,
        vendor
    )
(
    cisco_df["mapped_product_family"],
    cisco_df["missing_model"],
    cisco_df["status"],
    cisco_df["vendor"]
) = zip(*cisco_df["extracted_models"].apply(match_row))

# -------------------------------------------------
# 6️⃣ Save output
# -------------------------------------------------
cisco_df.to_csv("cisco_intel_amd_merged_output.csv", index=False)
print("✅ Saved cisco_intel_amd_merged_output.csv")
