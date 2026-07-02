import pandas as pd
import re
import numpy as np
# Cleaning functions
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
def normalize_family(text):
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[®™Â]", "", text)
    text = re.sub(r"\bgeneration\b", "gen", text)
    text = text.replace("processors", "processor")
    text = re.sub(r"\s+", " ", text).strip()
    return text
# model number extractor
def extract_model_number(text):
    m = re.search(r"\b[a-z]?\d{3,5}[a-z]?\b", text)
    return m.group(0) if m else None
# generation extractor
def extract_generation(text):
    m = re.search(r"\b(\d)(st|nd|rd|th)\s+gen\b", text)
    return m.group(1) if m else None
# list cleaner
def clean_list(values):
    return list({
        v for v in values
        if v is not None and not (isinstance(v, float) and np.isnan(v))
    })
# Load files
print("Loading files...")
gigabyte_df = pd.read_csv("30082025_reordered_file.csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)
amd_df = pd.read_csv("amd_processor_import_db (3).csv", low_memory=False)
#  Prepare INTEL reference
intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name)
intel_df["clean_product_family"] = intel_df["product_family"].apply(clean_processor_name)
intel_df["model_number"] = intel_df["clean_product_name"].apply(extract_model_number)

intel_name_to_family = dict(zip(intel_df["clean_product_name"], intel_df["product_family"]))
intel_family_to_family = dict(zip(intel_df["clean_product_family"], intel_df["product_family"]))
intel_model_to_family = dict(zip(intel_df["model_number"], intel_df["product_family"]))

intel_product_name_set = set(intel_name_to_family)
intel_product_family_set = set(intel_family_to_family)
intel_model_set = set(intel_model_to_family)
# Prepare AMD reference
amd_df["clean_product_name"] = amd_df["product_name"].apply(clean_processor_name)
amd_df["clean_processor_series"] = amd_df["processor_series"].apply(clean_processor_name)

amd_name_to_family = dict(zip(amd_df["clean_product_name"], amd_df["product_family"]))
amd_series_to_family = dict(zip(amd_df["clean_processor_series"], amd_df["product_family"]))

amd_product_name_set = set(amd_name_to_family)
amd_processor_series_set = set(amd_series_to_family)
#  Clean Gigabyte data
gigabyte_df["clean_processor"] = gigabyte_df["processor"].apply(get_clean_processor_list)
gigabyte_df["clean_gigabyte_family"] = gigabyte_df["processor_family"].apply(get_clean_processor_list)
#  Matching logic (Intel + AMD)
def match_processors(processors):
    matched_names = []
    matched_families = []

    for p in processors:
        model = extract_model_number(p)
        gen = extract_generation(p)
        # INTEL 
        if p in intel_product_name_set:
            matched_names.append(p)
            matched_families.append(intel_name_to_family[p])
            continue
        for fam in intel_product_family_set:
            fam_gen = extract_generation(fam)
            base_p = p.replace(f"{gen} gen", "").strip() if gen else p
            if base_p in fam and (not gen or fam_gen == gen):
                matched_names.append(p)
                matched_families.append(intel_family_to_family[fam])
                break
        else:
            if model and model in intel_model_set:
                matched_names.append(model)
                matched_families.append(intel_model_to_family[model])
                continue
        # AMD
        if p in amd_product_name_set:
            matched_names.append(p)
            matched_families.append(amd_name_to_family[p])
            continue
        if p in amd_processor_series_set:
            matched_names.append(p)
            matched_families.append(amd_series_to_family[p])

    return clean_list(matched_names), clean_list(matched_families)
# Apply matching
(gigabyte_df["mapped_product_name"],gigabyte_df["mapped_product_family"]
) = zip(*gigabyte_df["clean_processor"].apply(match_processors))
# Missing family column
def get_missing_families(row):
    mapped_families = {normalize_family(f) for f in row["mapped_product_family"]}
    gigabyte_families = {normalize_family(f) for f in row["clean_gigabyte_family"]}
    if not gigabyte_families or not mapped_families:
        return []
    return sorted(gigabyte_families - mapped_families)
gigabyte_df["missing_family"] = gigabyte_df.apply(get_missing_families, axis=1)
#  Status logic
def get_status(row):
    total = len(row["clean_processor"])
    mapped_families = {normalize_family(f) for f in row["mapped_product_family"]}
    gigabyte_families = {normalize_family(f) for f in row["clean_gigabyte_family"]}
    if total == 0:
        return "missing"
    if not gigabyte_families and mapped_families:
        return "No family is mapped"
    if not mapped_families:
        return "Family is not found"
    if not mapped_families.intersection(gigabyte_families):
        return "mismatch"
    if not gigabyte_families.issubset(mapped_families):
        missing = gigabyte_families - mapped_families
        return f"{len(missing)} family missing"
    return "match"
gigabyte_df["status"] = gigabyte_df.apply(get_status, axis=1)
# save output
gigabyte_df.to_csv("rework_intel_amd_matched_output.csv", index=False)
print("Saved rework_intel_amd_matched_output.csv")
