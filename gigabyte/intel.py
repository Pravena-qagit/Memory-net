import pandas as pd
import re
# Cleaning functions
def clean_processor_name(name):
    name = str(name).lower()
    name = re.sub(r"\bgeneration\b", "gen", name)
    name = re.sub(r"\bprocessors\b", "processor", name)
    name = re.sub(r"\b(soc|quad-core|dual-core|single-core|i[- ]?series)\b", "", name)
    name = re.sub(r"[^\w\s-]", "", name)
    return " ".join(name.strip().split())
# clean processor list extractor
def get_clean_processor_list(x):
    try:
        proc_list = eval(x)
        if not isinstance(proc_list, list):
            proc_list = [str(proc_list)]
    except:
        proc_list = [str(x)]
    return [clean_processor_name(p) for p in proc_list if p]
# model number normalizer
def extract_model_number(text):
    m = re.search(r"\b[a-z]?\d{3,5}[a-z]?\b", text)
    return m.group(0) if m else None
# generation extractor
def extract_generation(text):
    m = re.search(r"\b(\d)(st|nd|rd|th)\s+gen\b", text)
    return m.group(1) if m else None
# load files
print("Loading files...")
gigabyte_df = pd.read_csv("30082025_reordered_file.csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)
# clean INTEL reference
intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name)
intel_df["clean_product_family"] = intel_df["product_family"].apply(clean_processor_name)
intel_df["model_number"] = intel_df["clean_product_name"].apply(extract_model_number)
intel_df["generation"] = intel_df["clean_product_family"].apply(extract_generation)

intel_product_name_set = set(intel_df["clean_product_name"].dropna())
intel_product_family_set = set(intel_df["clean_product_family"].dropna())
intel_model_set = set(intel_df["model_number"].dropna())

product_name_to_family = dict(zip(intel_df["clean_product_name"], intel_df["product_family"]))
family_to_family = dict(zip(intel_df["clean_product_family"], intel_df["product_family"]))
model_to_family = dict(zip(intel_df["model_number"], intel_df["product_family"]))
# GIGABYTE clean processor list
gigabyte_df["clean_processor"] = gigabyte_df["processor"].apply(get_clean_processor_list)
# Intel exact match function
def exact_intel_match_processor_list(lst):
    matched_names, matched_families, match_sources = [], [], []

    for p in lst:
        model = extract_model_number(p)
        gen = extract_generation(p)
        # Level 1: product_name exact
        if p in intel_product_name_set:
            matched_names.append(p)
            matched_families.append(product_name_to_family.get(p))
            match_sources.append("product_name")
            continue
        # Level 2: generation-aware family match (SAFE)
        fam_candidates = []

        for fam in intel_product_family_set:
            base_p = p
            fam_gen = extract_generation(fam)
            # remove generation text ONLY if present
            if gen:
                base_p = p.replace(f"{gen} gen", "").strip()

            if base_p in fam:
                # exact generation match → highest priority
                if gen and fam_gen == gen:
                    fam_candidates.insert(0, fam)
                else:
                    fam_candidates.append(fam)

        if fam_candidates:
            chosen_fam = fam_candidates[0]
            matched_names.append(p)
            matched_families.append(family_to_family.get(chosen_fam))
            match_sources.append("product_family")
            continue
        # Level 3: model number
        if model and model in intel_model_set:
            matched_names.append(model)
            matched_families.append(model_to_family.get(model))
            match_sources.append("model_number")
    return (
        list(set(matched_names)),
        list(set(filter(None, matched_families))),
        list(set(match_sources))
    )
# Apply matching logic
(
    gigabyte_df["mapped_product_name"],
    gigabyte_df["mapped_product_family"],
    gigabyte_df["match_source"]
) = zip(*gigabyte_df["clean_processor"].apply(exact_intel_match_processor_list))
# missing processors column
gigabyte_df["missing_processors"] = gigabyte_df.apply(lambda r: [p for p in r["clean_processor"] if p not in r["mapped_product_name"]], axis=1)
# status logic
def get_status(row):
    total = len(row["clean_processor"])
    matched = len(row["mapped_product_name"])
    if not row["clean_processor"] or all(p in ["", "nan"] for p in row["clean_processor"]):
        return "missing"
    if matched == 0:
        return "Family is not found"
    if matched < total:
        return f"{total - matched} of {total} processors missing"
    return "match"
gigabyte_df["status"] = gigabyte_df.apply(get_status, axis=1)
# save final output
gigabyte_df.to_csv("final_intel_matched_output.csv", index=False)
print("Saved final_intel_matched_output.csv ")
