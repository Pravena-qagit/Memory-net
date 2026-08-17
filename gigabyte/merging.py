import pandas as pd
import re
import numpy as np

# -------------------------------------------------
# 1️⃣ Cleaning helpers
# -------------------------------------------------
def clean_processor_name(name):
    name = str(name).lower()
    name = re.sub(r"\bgeneration\b", "gen", name)
    name = re.sub(r"\bprocessors\b", "processor", name)
    name = re.sub(r"\b(soc|quad-core|dual-core|single-core|i[- ]?series)\b", "", name)
    name = re.sub(r"[^\w\s-]", "", name)
    return " ".join(name.strip().split())


def get_clean_processor_list(x):
    try:
        proc_list = eval(x)
        if not isinstance(proc_list, list):
            proc_list = [str(proc_list)]
    except:
        proc_list = [str(x)]

    return [
        clean_processor_name(p)
        for p in proc_list
        if p and str(p).lower() not in ["nan", "none"]
    ]


# -------------------------------------------------
# 2️⃣ Extract helpers
# -------------------------------------------------
def extract_model_number(text):
    m = re.search(r"\b[a-z]?\d{3,5}[a-z]?\b", text)
    return m.group(0) if m else None


def extract_generation(text):
    m = re.search(r"\b(\d)(st|nd|rd|th)\s+gen\b", text)
    return m.group(1) if m else None


# -------------------------------------------------
# 3️⃣ Utility: remove NaN safely
# -------------------------------------------------
def clean_family_list(values):
    return list({
        v for v in values
        if v is not None and not (isinstance(v, float) and np.isnan(v))
    })


# -------------------------------------------------
# 4️⃣ Load files
# -------------------------------------------------
print("Loading files...")
gigabyte_df = pd.read_csv("30082025_reordered_file.csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)
amd_df = pd.read_csv("amd_processor_import_db (3).csv", low_memory=False)


# -------------------------------------------------
# 5️⃣ Clean reference data
# -------------------------------------------------
# ---- Intel
intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name)
intel_df["clean_product_family"] = intel_df["product_family"].apply(clean_processor_name)
intel_df["model_number"] = intel_df["clean_product_name"].apply(extract_model_number)

intel_product_name_set = set(intel_df["clean_product_name"].dropna())
intel_product_family_set = set(intel_df["clean_product_family"].dropna())
intel_model_set = set(intel_df["model_number"].dropna())

intel_name_to_family = dict(zip(intel_df["clean_product_name"], intel_df["product_family"]))
intel_family_to_family = dict(zip(intel_df["clean_product_family"], intel_df["product_family"]))
intel_model_to_family = dict(zip(intel_df["model_number"], intel_df["product_family"]))

# ---- AMD
amd_df["clean_product_name"] = amd_df["product_name"].apply(clean_processor_name)
amd_df["clean_processor_series"] = amd_df["processor_series"].apply(clean_processor_name)

amd_product_name_set = set(amd_df["clean_product_name"].dropna())
amd_processor_series_set = set(amd_df["clean_processor_series"].dropna())

amd_name_to_family = dict(zip(amd_df["clean_product_name"], amd_df["product_family"]))
amd_series_to_family = dict(zip(amd_df["clean_processor_series"], amd_df["product_family"]))


# -------------------------------------------------
# 6️⃣ Clean Gigabyte processors
# -------------------------------------------------
gigabyte_df["clean_processor"] = gigabyte_df["processor"].apply(get_clean_processor_list)


# -------------------------------------------------
# 7️⃣ INTEL + AMD MATCH LOGIC
# -------------------------------------------------
def match_processors(lst):
    matched_names = []
    matched_families = []
    match_sources = []

    for p in lst:
        model = extract_model_number(p)
        gen = extract_generation(p)

        # =====================
        # INTEL MATCHING
        # =====================
        if p in intel_product_name_set:
            matched_names.append(p)
            matched_families.append(intel_name_to_family.get(p))
            match_sources.append("intel_product_name")
            continue

        fam_candidates = []
        for fam in intel_product_family_set:
            fam_gen = extract_generation(fam)
            base_p = p.replace(f"{gen} gen", "").strip() if gen else p

            if base_p in fam:
                if gen and fam_gen == gen:
                    fam_candidates.insert(0, fam)
                else:
                    fam_candidates.append(fam)

        if fam_candidates:
            chosen = fam_candidates[0]
            matched_names.append(p)
            matched_families.append(intel_family_to_family.get(chosen))
            match_sources.append("intel_product_family")
            continue

        if model and model in intel_model_set:
            matched_names.append(model)
            matched_families.append(intel_model_to_family.get(model))
            match_sources.append("intel_model_number")
            continue

        # =====================
        # AMD MATCHING
        # =====================
        if p in amd_product_name_set:
            matched_names.append(p)
            matched_families.append(amd_name_to_family.get(p))
            match_sources.append("amd_product_name")
            continue

        if p in amd_processor_series_set:
            matched_names.append(p)
            matched_families.append(amd_series_to_family.get(p))
            match_sources.append("amd_processor_series")

    return (
        list(set(matched_names)),
        clean_family_list(matched_families),
        list(set(match_sources))
    )


# -------------------------------------------------
# 8️⃣ Apply matching
# -------------------------------------------------
(
    gigabyte_df["mapped_product_name"],
    gigabyte_df["mapped_product_family"],
    gigabyte_df["match_source"]
) = zip(*gigabyte_df["clean_processor"].apply(match_processors))


# -------------------------------------------------
# 9️⃣ Missing processors
# -------------------------------------------------
gigabyte_df["missing_processors"] = gigabyte_df.apply(
    lambda r: [p for p in r["clean_processor"] if p not in r["mapped_product_name"]],
    axis=1
)


# -------------------------------------------------
# 🔟 Status logic (WITH mismatch)
# -------------------------------------------------
def get_status(row):
    total = len(row["clean_processor"])
    matched = len(row["mapped_product_name"])
    families = row["mapped_product_family"]

    if total == 0:
        return "missing"
    if matched == 0:
        return "Family is not found"
    if matched > 0 and not families:
        return "mismatch"
    if matched < total:
        return f"{total - matched} of {total} family missing"
    return "match"


gigabyte_df["status"] = gigabyte_df.apply(get_status, axis=1)


# -------------------------------------------------
# 🔟 Save output
# -------------------------------------------------
gigabyte_df.to_csv("final_intel_amd_matched_output.csv", index=False)
print("Saved final_intel_amd_matched_output.csv ✅")
