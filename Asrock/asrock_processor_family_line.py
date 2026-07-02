import pandas as pd
import re
import numpy as np
import ast

# ==================================================
# Cleaning functions
# ==================================================

def clean_processor_name(name):

    name = str(name).lower()

    name = re.sub(r"\bgeneration\b", "gen", name)
    name = re.sub(r"\bprocessors\b", "processor", name)

    name = re.sub(r"\b(soc|quad-core|dual-core|single-core|i[- ]?series)\b", "", name)

    name = re.sub(r"[®™Â]", "", name)

    name = re.sub(r"[^\w\s-]", " ", name)

    return " ".join(name.split())


def get_clean_processor_list(x):

    if pd.isna(x):
        return []

    x = str(x)

    try:
        proc_list = ast.literal_eval(x)

        if not isinstance(proc_list, list):
            proc_list = [proc_list]

    except:
        proc_list = [x]

    cleaned = []

    for p in proc_list:

        if p and str(p).lower() not in ("nan", "none"):

            p = str(p).strip()

            p = p.strip('"').strip("'")

            cleaned.append(clean_processor_name(p))

    return cleaned


# ==================================================
# NORMALIZATION
# ==================================================

def normalize_family(text):

    if not text:
        return ""

    text = str(text).lower()

    text = re.sub(r"[®™Â]", "", text)
    text = re.sub(r"[()]", "", text)

    text = text.replace("-", " ")

    text = re.sub(r"\bgeneration\b", "gen", text)

    text = text.replace("processors", "processor")

    text = re.sub(r"[^\w\s]", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==================================================
# CPU MODEL EXTRACTOR
# ==================================================

def extract_cpu_model(text):

    if not text:
        return None

    text = text.lower()

    patterns = [

        (r"\b(i[3579])[-\s]?(\d{4,5}[a-z]{0,2})\b",
         lambda m: f"{m.group(1)} {m.group(2)}"),

        (r"\b(e\d|w\d|d\d)[-\s]?(\d{4})(?:\s*(v\d))?\b",
         lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}".strip() if m.group(3) else f"{m.group(1)} {m.group(2)}"),

        (r"\bxeon\s+(gold|silver|platinum|bronze)\s+(\d{4,5}[a-z]{0,2})\b",
         lambda m: f"{m.group(1)} {m.group(2)}"),

        (r"\bryzen\s+([3579])\s+(\d{4}[a-z]{0,2})\b",
         lambda m: f"{m.group(1)} {m.group(2)}"),

        (r"\bepyc\s+(\d{4})\b",
         lambda m: f"epyc {m.group(1)}"),

        (r"\bthreadripper(?:\s+pro)?\s+(\d{4,5}[a-z]{0,2})\b",
         lambda m: m.group(1)),
    ]

    for pattern, formatter in patterns:

        m = re.search(pattern, text)

        if m:
            return formatter(m)

    return None


def extract_generation(text):

    m = re.search(r"\b(\d)(st|nd|rd|th)\s+gen\b", text)

    return m.group(1) if m else None


def clean_list(values):

    return list({
        v for v in values
        if v is not None and not (isinstance(v, float) and np.isnan(v))
    })


# ==================================================
# LOAD FILES
# ==================================================

print("Loading files...")

asrock_df = pd.read_csv("24042026_asrock_dimm_ranks.csv", low_memory=False)
intel_df = pd.read_csv("12022026_intel_db_import.csv", low_memory=False)
amd_df = pd.read_csv("09022026_amd_db_import (1).csv", low_memory=False)


# ==================================================
# PREPARE INTEL REFERENCE
# ==================================================

intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name)
intel_df["clean_product_family"] = intel_df["product_family"].apply(clean_processor_name)

intel_df["model_token"] = intel_df["clean_product_name"].apply(extract_cpu_model)

intel_name_to_family = dict(zip(intel_df["clean_product_name"], intel_df["product_family"]))
intel_model_to_family = dict(zip(intel_df["model_token"], intel_df["product_family"]))

intel_name_to_line = dict(zip(intel_df["clean_product_name"], intel_df["product_line"]))
intel_model_to_line = dict(zip(intel_df["model_token"], intel_df["product_line"]))

intel_product_name_set = set(intel_name_to_family)
intel_model_set = set(intel_model_to_family)


# ==================================================
# PREPARE AMD REFERENCE
# ==================================================

amd_df["clean_product_name"] = amd_df["product_name"].apply(clean_processor_name)
amd_df["clean_processor_series"] = amd_df["processor_series"].apply(clean_processor_name)

amd_df["model_token"] = amd_df["clean_product_name"].apply(extract_cpu_model)

amd_name_to_family = dict(zip(amd_df["clean_product_name"], amd_df["product_family"]))
amd_model_to_family = dict(zip(amd_df["model_token"], amd_df["product_family"]))

amd_name_to_line = dict(zip(amd_df["clean_product_name"], amd_df["processor_series"]))
amd_model_to_line = dict(zip(amd_df["model_token"], amd_df["processor_series"]))

amd_product_name_set = set(amd_name_to_family)
amd_model_set = set(amd_model_to_family)


# ==================================================
# CLEAN ASROCK DATA
# ==================================================

asrock_df["clean_processor"] = asrock_df["processor"].apply(get_clean_processor_list)
asrock_df["clean_asrock_family"] = asrock_df["processor_family"].apply(get_clean_processor_list)
asrock_df["clean_asrock_line"] = asrock_df["processor_line"].apply(get_clean_processor_list)


# ==================================================
# MATCHING LOGIC
# ==================================================

def match_processors(processors):

    matched_names = []
    matched_families = []
    matched_lines = []

    for p in processors:

        model = extract_cpu_model(p)

        if p in intel_product_name_set:
            matched_names.append(p)
            matched_families.append(intel_name_to_family[p])
            matched_lines.append(intel_name_to_line[p])
            continue

        if model and model in intel_model_set:
            matched_names.append(model)
            matched_families.append(intel_model_to_family[model])
            matched_lines.append(intel_model_to_line[model])
            continue

        if p in amd_product_name_set:
            matched_names.append(p)
            matched_families.append(amd_name_to_family[p])
            # matched_lines.append(amd_name_to_line[p])
            continue

        if model and model in amd_model_set:
            matched_names.append(model)
            matched_families.append(amd_model_to_family[model])
            # matched_lines.append(amd_model_to_line[model])

    return (
        clean_list(matched_names),
        clean_list(matched_families),
        clean_list(matched_lines)
    )


(
    asrock_df["mapped_product_name"],
    asrock_df["mapped_product_family"],
    asrock_df["mapped_product_line"]
) = zip(*asrock_df["clean_processor"].apply(match_processors))


# ==================================================
# MISSING FAMILY
# ==================================================

def get_missing_families(row):

    mapped = {normalize_family(f) for f in row["mapped_product_family"]}
    asrock = {normalize_family(f) for f in row["clean_asrock_family"]}

    if not mapped:
        return []

    return sorted(mapped - asrock)


asrock_df["missing_family"] = asrock_df.apply(get_missing_families, axis=1)


# ==================================================
# MISSING LINE
# ==================================================

def get_missing_lines(row):

    mapped = {normalize_family(l) for l in row["mapped_product_line"]}
    asrock = {normalize_family(l) for l in row["clean_asrock_line"]}

    if not mapped:
        return []

    return sorted(mapped - asrock)


asrock_df["missing_line"] = asrock_df.apply(get_missing_lines, axis=1)


# ==================================================
# NEW COLUMN REQUESTED BY DEVELOPER
# ==================================================

def get_missing_status(row):

    fam_missing = len(row["missing_family"])
    line_missing = len(row["missing_line"])

    if fam_missing > 0 and line_missing > 0:
        return "family and line missing"

    if fam_missing > 0:
        return "family missing"

    if line_missing > 0:
        return "line missing"

    return "none"


asrock_df["missing_status"] = asrock_df.apply(get_missing_status, axis=1)


# ==================================================
# ORIGINAL STATUS
# ==================================================

def get_status(row):

    total = len(row["clean_processor"])

    if total == 0:
        return "missing"

    if len(row["clean_asrock_family"]) == 0 and len(row["mapped_product_family"]) > 0:
        return "No family is mapped in main CSV"

    if len(row["mapped_product_family"]) == 0:
        return "Family is not found"

    if len(row["missing_family"]) > 0:
        return f"{len(row['missing_family'])} family missing"

    if len(row["missing_line"]) > 0:
        return f"{len(row['missing_line'])} line missing"

    return "match"


asrock_df["status"] = asrock_df.apply(get_status, axis=1)


# ==================================================
# OUTPUT
# ==================================================

output_columns = [
    "server_description",
    "server_specification",
    "processor",
    "processor_family",
    "processor_line",
    "clean_processor",
    "clean_asrock_family",
    "clean_asrock_line",
    "mapped_product_name",
    "mapped_product_family",
    "mapped_product_line",
    "missing_family",
    "missing_line",
    "missing_status",
    "status"
]

output_df = asrock_df[output_columns]


list_columns = [
    "clean_processor",
    "clean_asrock_family",
    "clean_asrock_line",
    "mapped_product_name",
    "mapped_product_family",
    "mapped_product_line",
    "missing_family",
    "missing_line"
]

for col in list_columns:
    output_df[col] = output_df[col].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else x
    )


output_df.to_csv("Asrock_intel_amd_matched_output.csv", index=False)

print("Saved Asrock_intel_amd_matched_output.csv")