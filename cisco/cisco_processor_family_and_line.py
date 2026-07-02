import pandas as pd
import re
import ast

# =====================================================
# 1️⃣ Load files
# =====================================================
print("Loading files...")
cisco_df = pd.read_csv("cisco_db_import.csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)
amd_df = pd.read_csv("amd_processor_import_db (3).csv", low_memory=False)

# =====================================================
# 2️⃣ Intel normalization
# =====================================================
def normalize_intel_model(model):
    if pd.isna(model):
        return None
    model = str(model).upper().strip()
    model = re.sub(r"\s+V", "V", model)
    model = model.replace(" ", "")
    model = re.sub(r"[+=]+$", "", model)
    return model

# =====================================================
# 3️⃣ Intel lookup
# =====================================================
intel_df["model_number_norm"] = intel_df["model_number"].apply(normalize_intel_model)

intel_lookup = {
    row["model_number_norm"]: (row["product_family"], row["product_line"])
    for _, row in intel_df.iterrows()
}
intel_model_set = set(intel_lookup.keys())

# =====================================================
# 4️⃣ AMD EPYC lookup
# =====================================================
def extract_amd_model(product_name):
    if pd.isna(product_name):
        return None

    text = str(product_name)

    if re.search(r'\b[A-Z]\d-\d+\b', text):
        return None

    match = re.search(r'\b(\d{4,5}[A-Z]?)\b', text)
    return match.group(1) if match else None

amd_df["amd_model"] = amd_df["product_name"].apply(extract_amd_model)

amd_lookup = {
    row["amd_model"]: row["product_family"]
    for _, row in amd_df.iterrows()
    if pd.notna(row["amd_model"])
}
amd_model_set = set(amd_lookup.keys())

# =====================================================
# 5️⃣ Cisco processor extraction (CORRUPTION SAFE)
# =====================================================
def extract_cisco_models(text):
    if pd.isna(text):
        return []

    raw = str(text)

    tokens = []

    # ---------- TRY structured parsing ----------
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            tokens = parsed
        else:
            tokens = [parsed]
    except Exception:
        tokens = []

    cleaned = []

    # ---------- If parsing failed or tokens are bad → REGEX FALLBACK ----------
    if not tokens or any(len(str(t)) > 50 for t in tokens):
        # Extract ALL valid model-like patterns directly
        tokens = re.findall(r"\bA?\d{4,5}[A-Z]?\b", raw)

    # ---------- Normalize ----------
    for token in tokens:
        token = str(token).strip().strip("'\"")

        # Remove trailing junk
        token = re.sub(r"[+=]+$", "", token)

        token = token.replace(" ", "").upper()

        # Remove leading AMD A
        if re.fullmatch(r"A\d{4,5}[A-Z]?", token):
            token = token[1:]

        cleaned.append(token)

    return sorted(set(cleaned))

cisco_df["extracted_model_numbers"] = cisco_df["processor"].apply(extract_cisco_models)

# =====================================================
# 6️⃣ TRUE MATCH / MISMATCH LOGIC
# =====================================================
def match_row(row):
    models = row["extracted_model_numbers"]
    cisco_family = row.get("cisco_product_family")

    if not models:
        return [], [], [], "missing", "missing"

    vendor_set = set()
    fam_set, line_set, missing = set(), set(), []

    total = 0
    matched = 0

    for m in models:
        # ---------- INTEL ----------
        if m in intel_model_set or re.search(r"E\d-\d{4}", m):
            total += 1
            vendor_set.add("Intel")

            if m in intel_model_set:
                fam, line = intel_lookup[m]
                fam_set.add(fam)
                line_set.add(line)
                matched += 1
            else:
                missing.append(m)

        # ---------- AMD ----------
        elif re.fullmatch(r"\d{4,5}[A-Z]?", m):
            total += 1
            vendor_set.add("AMD")

            if m in amd_model_set:
                fam_set.add(amd_lookup[m])
                matched += 1
            else:
                missing.append(m)

    if total == 0:
        status = "missing"
    elif matched == 0:
        status = "Family is not found"
    elif matched < total:
        status = "partial_match"
    elif cisco_family and fam_set:
        status = "match" if cisco_family in fam_set else "mismatch"
    else:
        status = "match"

    return (
        list(fam_set),
        list(line_set),
        missing,
        ", ".join(sorted(vendor_set)),
        status
    )

(
    cisco_df["mapped_product_family"],
    cisco_df["mapped_product_line"],
    cisco_df["missing_model_numbers"],
    cisco_df["vendor"],
    cisco_df["status"]
) = zip(*cisco_df.apply(match_row, axis=1))

# =====================================================
# 7️⃣ Save output
# =====================================================
output_file = "cisco_remerge_output.csv"
cisco_df.to_csv(output_file, index=False)
print(f"✅ Saved {output_file}")
