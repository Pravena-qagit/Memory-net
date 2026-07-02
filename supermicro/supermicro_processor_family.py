import pandas as pd
import re
import numpy as np
import ast

# ==================================================
# CLEANING FUNCTIONS
# ==================================================

def clean_processor_name(name):
    name = str(name).lower()
    name = re.sub(r"\b\d+x\b", "", name)
    name = re.sub(r"\bdual\b|\bsingle\b", "", name)
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
            p = str(p).strip().strip('"').strip("'")
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
        (r"\b(i[3579])[-\s]?(\d{4,5}[a-z]{0,2})\b", lambda m: f"{m.group(1)} {m.group(2)}"),
        (r"\bxeon\s+(gold|silver|platinum|bronze)\s+(\d{4,5}[a-z]{0,2})\b", lambda m: f"{m.group(1)} {m.group(2)}"),
        (r"\bxeon\s+(?:scalable\s+)?(\d{4,5}[a-z]{0,2})\b", lambda m: m.group(1)),
        (r"\b(e\d|w\d|d\d)[-\s]?(\d{4})(?:\s*(v\d))?\b",
         lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}".strip() if m.group(3) else f"{m.group(1)} {m.group(2)}"),
        (r"\bryzen\s+([3579])\s+(\d{4}[a-z]{0,2})\b", lambda m: f"{m.group(1)} {m.group(2)}"),
        (r"\bepyc\s+(\d{4})\b", lambda m: f"epyc {m.group(1)}"),
        (r"\bthreadripper(?:\s+pro)?\s+(\d{4,5}[a-z]{0,2})\b", lambda m: m.group(1)),
    ]

    for pattern, formatter in patterns:
        m = re.search(pattern, text)
        if m:
            return formatter(m)
    return None


# ==================================================
# UTIL
# ==================================================

def clean_list(values):
    return list({
        v for v in values
        if v is not None and not (isinstance(v, float) and np.isnan(v))
    })


# ==================================================
# DYNAMIC SERIES MATCH
# ==================================================

def dynamic_series_match(p, ref_names, name_to_family, name_to_line):
    words = set(p.split())
    best_family = None
    best_line = None
    best_score = 0

    for ref in ref_names:
        ref_words = set(ref.split())
        score = len(words & ref_words)

        if score > best_score:
            best_score = score
            best_family = name_to_family.get(ref)
            best_line = name_to_line.get(ref)

    return best_family, best_line


# ==================================================
# LOAD FILES
# ==================================================

print("Loading files...")

supermicro_df = pd.read_csv("supermicro_max_memory_speed.csv", low_memory=False)
intel_df = pd.read_csv("12022026_intel_db_import.csv", low_memory=False)
amd_df = pd.read_csv("09022026_amd_db_import (1).csv", low_memory=False)


# ==================================================
# PREPARE INTEL
# ==================================================

intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name)
intel_df["model_token"] = intel_df["clean_product_name"].apply(extract_cpu_model)

intel_name_to_family = dict(zip(intel_df["clean_product_name"], intel_df["product_family"]))
intel_name_to_line = dict(zip(intel_df["clean_product_name"], intel_df["product_line"]))

intel_product_name_set = set(intel_name_to_family)
intel_xeon_refs = [n for n in intel_product_name_set if "xeon" in n]


# ==================================================
# PREPARE AMD
# ==================================================

amd_df["clean_product_name"] = amd_df["product_name"].apply(clean_processor_name)
amd_df["model_token"] = amd_df["clean_product_name"].apply(extract_cpu_model)

amd_name_to_family = dict(zip(amd_df["clean_product_name"], amd_df["product_family"]))
amd_name_to_line = dict(zip(amd_df["clean_product_name"], amd_df["processor_series"]))

amd_product_name_set = set(amd_name_to_family)
amd_epyc_refs = [n for n in amd_product_name_set if "epyc" in n]


# ==================================================
# CLEAN MAIN DATA
# ==================================================

supermicro_df["clean_processor"] = supermicro_df["processor"].apply(get_clean_processor_list)
supermicro_df["clean_supermicro_family"] = supermicro_df["processor_family"].apply(get_clean_processor_list)
supermicro_df["clean_supermicro_line"] = supermicro_df["processor_line"].apply(get_clean_processor_list)


# ==================================================
# MATCHING (ONLY EXACT MATCH, IGNORE UNMATCHED)
# ==================================================

def match_processors_with_trace(processors):

    matched_names = []
    matched_families = []
    matched_lines = []
    trace = []

    for p in processors:

        fam = None
        line = None
        name = None

        # ONLY exact product_name match
        if p in intel_product_name_set:
            name = p
            fam = intel_name_to_family[p]
            line = intel_name_to_line[p]

        elif p in amd_product_name_set:
            name = p
            fam = amd_name_to_family[p]
            line = amd_name_to_line[p]

        # if not found in either csv, ignore it completely
        else:
            continue

        matched_names.append(name)
        if fam:
            matched_families.append(fam)
        if line:
            matched_lines.append(line)

        trace.append((p, fam, line))

    return (
        clean_list(matched_names),
        clean_list(matched_families),
        clean_list(matched_lines),
        trace
    )


(
    supermicro_df["mapped_product_name"],
    supermicro_df["mapped_product_family"],
    supermicro_df["mapped_product_line"],
    supermicro_df["mapping_trace"]
) = zip(*supermicro_df["clean_processor"].apply(match_processors_with_trace))


# ==================================================
# MISSING
# ==================================================

def get_missing_families(row):
    mapped = {normalize_family(f) for f in row["mapped_product_family"]}
    actual = {normalize_family(f) for f in row["clean_supermicro_family"]}
    return sorted(mapped - actual)


def get_missing_lines(row):
    mapped = {normalize_family(l) for l in row["mapped_product_line"]}
    actual = {normalize_family(l) for l in row["clean_supermicro_line"]}
    return sorted(mapped - actual)


supermicro_df["missing_family"] = supermicro_df.apply(get_missing_families, axis=1)
supermicro_df["missing_line"] = supermicro_df.apply(get_missing_lines, axis=1)


# ==================================================
# 🔥 UNMAPPED PROCESSOR (ACCURATE)
# ==================================================

def get_unmapped_processors(row):

    missing_fams = {normalize_family(f) for f in row["missing_family"]}
    missing_lines = {normalize_family(l) for l in row["missing_line"]}

    result = []

    for p, fam, line in row["mapping_trace"]:

        fam_n = normalize_family(fam)
        line_n = normalize_family(line)

        if fam_n in missing_fams or line_n in missing_lines:
            result.append(p)

    return clean_list(result)


supermicro_df["unmapped_processor"] = supermicro_df.apply(get_unmapped_processors, axis=1)


def get_status(row):

    mapped_fam = {normalize_family(f) for f in row["mapped_product_family"]}
    actual_fam = {normalize_family(f) for f in row["clean_supermicro_family"]}

    mapped_line = {normalize_family(l) for l in row["mapped_product_line"]}
    actual_line = {normalize_family(l) for l in row["clean_supermicro_line"]}

    # ✅ Separate differences
    missing_fam = mapped_fam - actual_fam
    extra_fam   = actual_fam - mapped_fam

    missing_line = mapped_line - actual_line
    extra_line   = actual_line - mapped_line

    def plural(word, count):
        return word if count == 1 else word + "s"

    messages = []

    # 🔴 No mapping at all
    if not mapped_fam and not mapped_line:
        return "no match"

    # ===== FAMILY =====
    if missing_fam:
        messages.append(f"{len(missing_fam)} {plural('family', len(missing_fam))} missing")

    if extra_fam:
        messages.append(f"{len(extra_fam)} {plural('family', len(extra_fam))} mismatch")

    # ===== LINE =====
    if missing_line:
        messages.append(f"{len(missing_line)} {plural('line', len(missing_line))} missing")

    if extra_line:
        messages.append(f"{len(extra_line)} {plural('line', len(extra_line))} mismatch")

    # ✅ Perfect match
    if not messages:
        return "match"

    # ✅ Combine everything
    return " & ".join(messages)

supermicro_df["status"] = supermicro_df.apply(get_status, axis=1)


# ==================================================
# OUTPUT
# ==================================================

output_columns = [
    "server_description",
    "processor",
    "processor_family",
    "processor_line",
    "clean_processor",
    "clean_supermicro_family",
    "clean_supermicro_line",
    "mapped_product_name",
    "mapped_product_family",
    "mapped_product_line",
    "missing_family",
    "missing_line",
    "unmapped_processor",
    "status"
]

output_df = supermicro_df[output_columns].copy()

list_columns = [
    "clean_processor",
    "clean_supermicro_family",
    "clean_supermicro_line",
    "mapped_product_name",
    "mapped_product_family",
    "mapped_product_line",
    "missing_family",
    "missing_line",
    "unmapped_processor"
]

for col in list_columns:
    output_df[col] = output_df[col].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else x
    )

output_df.to_csv("processor_family&line_report.csv", index=False)

print("Saved processor_family&line_report.csv with unmapped processors 🚀")