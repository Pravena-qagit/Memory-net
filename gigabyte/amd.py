import pandas as pd
import re
import math

# -------------------------------------------------
# 1️⃣ Cleaning functions
# -------------------------------------------------
def clean_processor_name(name):
    name = re.sub(r"[^\w\s-]", "", str(name))
    name = name.strip()
    name = " ".join(name.split())
    return name.lower()

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


print("Loading files")

# -------------------------------------------------
# 2️⃣ Load data
# -------------------------------------------------
gigabyte_df = pd.read_csv("30082025_reordered_file.csv", low_memory=False)
amd_df = pd.read_csv("amd_processor_import_db (3).csv", low_memory=False)

# -------------------------------------------------
# 3️⃣ Clean AMD reference columns
# -------------------------------------------------
amd_df["clean_product_name"] = amd_df["product_name"].apply(clean_processor_name)
amd_df["clean_processor_series"] = amd_df["processor_series"].apply(clean_processor_name)

# -------------------------------------------------
# 4️⃣ Lookup structures
# -------------------------------------------------
amd_product_name_set = set(amd_df["clean_product_name"].dropna())
amd_processor_series_set = set(amd_df["clean_processor_series"].dropna())

product_name_to_family = dict(
    zip(amd_df["clean_product_name"], amd_df["product_family"])
)
series_to_family = dict(
    zip(amd_df["clean_processor_series"], amd_df["product_family"])
)

# -------------------------------------------------
# 5️⃣ Clean Gigabyte processors
# -------------------------------------------------
gigabyte_df["clean_processor"] = gigabyte_df["processor"].apply(
    get_clean_processor_list
)

# -------------------------------------------------
# 6️⃣ Exact match logic
# -------------------------------------------------
def exact_amd_match_processor_list(lst):
    matched_names = []
    matched_families = []
    match_sources = []

    for p in lst:
        # Level 1: product_name exact match
        if p in amd_product_name_set:
            matched_names.append(p)
            family = product_name_to_family.get(p)
            if family:
                matched_families.append(family)
            match_sources.append("product_name")

        # Level 2: processor_series exact match
        elif p in amd_processor_series_set:
            matched_names.append(p)
            family = series_to_family.get(p)
            if family:
                matched_families.append(family)
            match_sources.append("processor_series")

    return (
        list(set(matched_names)),
        list(set(matched_families)),
        list(set(match_sources))
    )

# -------------------------------------------------
# 7️⃣ Map results back to Gigabyte dataframe
# -------------------------------------------------
(
    gigabyte_df["mapped_product_name"],
    gigabyte_df["mapped_product_family"],
    gigabyte_df["match_source"]
) = zip(
    *gigabyte_df["clean_processor"].apply(exact_amd_match_processor_list)
)

# -------------------------------------------------
# 8️⃣ ADVANCED STATUS LOGIC ✅
# -------------------------------------------------
def get_status(row):
    clean_list = row["clean_processor"]
    matched_list = row["mapped_product_name"]

    total = len(clean_list)
    matched = len(matched_list)

    # No valid processors
    if not clean_list:
        return "missing"

    # Nothing matched
    if matched == 0:
        return "Family is not found"

    # Partial match
    if matched < total:
        return f"{total - matched} of {total} processors missing"

    # Full match
    return "match"

gigabyte_df["status"] = gigabyte_df.apply(get_status, axis=1)

# -------------------------------------------------
# 9️⃣ Save output
# -------------------------------------------------
gigabyte_df.to_csv("final_amd_matched_output.csv", index=False)
print("Saved final_amd_matched_output.csv")
