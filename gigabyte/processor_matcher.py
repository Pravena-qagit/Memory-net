import pandas as pd
import re
import numpy as np

# ==================================================
# CLEANING FUNCTIONS
# ==================================================

def clean_processor_name(name):
    if not name:
        return ""

    name = str(name).lower()

    # ---- normalize generation consistently ----
    name = re.sub(r"\b(\d+)(st|nd|rd|th)?\s*-?\s*generation\b", r"\1 gen", name)
    name = re.sub(r"\b(\d+)(st|nd|rd|th)?\s*-?\s*gen\b", r"\1 gen", name)

    # ---- normalize noise words ----
    name = re.sub(r"\bprocessors\b", "processor", name)
    name = re.sub(r"\b(soc|quad-core|dual-core|single-core|i[- ]?series)\b", "", name)

    # ---- remove symbols ----
    name = re.sub(r"[®™Â]", "", name)
    name = re.sub(r"[^\w\s-]", " ", name)

    return " ".join(name.split())


def get_clean_processor_list(x):
    try:
        proc_list = eval(x)
        if not isinstance(proc_list, list):
            proc_list = [proc_list]
    except:
        proc_list = [x]

    return [
        clean_processor_name(p)
        for p in proc_list
        if p and str(p).lower() not in ("nan", "none")
    ]


def normalize_family(text):
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[®™Â]", "", text)
    text = text.replace("processors", "processor")
    return " ".join(text.split())


# ==================================================
# CPU MODEL EXTRACTION
# ==================================================

def extract_cpu_model(text):
    if not text:
        return None

    text = text.lower()

    patterns = [
        (r"\b(i[3579])[-\s]?(\d{4,5}[a-z]{0,2})\b",
         lambda m: f"{m.group(1)} {m.group(2)}"),
    
        (r"\bxeon\s+w[-\s]?(\d{4,5}[a-z])\b",
        lambda m: f"w-{m.group(1)}"),

        (r"\b(e\d)[-\s]?(\d{4})(?:\s*(v\d))?\b",
         lambda m: f"{m.group(1)} {m.group(2)} {m.group(3) or ''}".strip()),

        (r"\bxeon\s+(gold|silver|platinum|bronze)\s+(\d{4,5})\b",
         lambda m: f"{m.group(1)} {m.group(2)}"),

        (r"\bryzen\s+([3579])\s+(\d{4}[a-z]{0,2})\b",
         lambda m: f"{m.group(1)} {m.group(2)}"),

        (r"\bthreadripper(?:\s+pro)?\s+(\d{4,5}[a-z]{0,2})\b",
         lambda m: m.group(1)),
    ]

    for pattern, formatter in patterns:
        m = re.search(pattern, text)
        if m:
            return formatter(m)
    return None


# ==================================================
# MODEL TOKEN EXTRACTION
# ==================================================

def extract_model_tokens(text):
    if not text:
        return []
    return re.findall(r"\b[a-z]?\d{3,5}[a-z]{0,2}\b", text.lower())


def is_socket_token(token):
    return token.isdigit() and len(token) == 4


def clean_list(values):
    return list({
        v for v in values
        if v is not None and not (isinstance(v, float) and np.isnan(v))
    })


# ==================================================
# LOAD FILES
# ==================================================

print("Loading files...")

gigabyte_df = pd.read_csv("02022026_gigabyte_db_import.csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)
amd_df = pd.read_csv("amd_processor_import_db (3).csv", low_memory=False)


# ==================================================
# INTEL LOOKUPS (family + line)
# ==================================================

intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name)

intel_name_to_family = dict(zip(
    intel_df["clean_product_name"], intel_df["product_family"]
))
intel_name_to_line = dict(zip(
    intel_df["clean_product_name"], intel_df["product_line"]
))

intel_model_to_family = {}
intel_model_to_line = {}

for _, row in intel_df.iterrows():
    model = extract_cpu_model(row["clean_product_name"])
    if model:
        intel_model_to_family[model] = row["product_family"]
        intel_model_to_line[model] = row["product_line"]

intel_model_token_to_family = {}
intel_model_token_to_line = {}

for _, row in intel_df.iterrows():
    for token in extract_model_tokens(row["clean_product_name"]):
        if not is_socket_token(token):
            intel_model_token_to_family[token] = row["product_family"]
            intel_model_token_to_line[token] = row["product_line"]


# ==================================================
# AMD LOOKUPS (family ONLY)
# ==================================================

amd_df["clean_product_name"] = amd_df["product_name"].apply(clean_processor_name)

amd_name_to_family = dict(zip(
    amd_df["clean_product_name"], amd_df["product_family"]
))

amd_model_to_family = {}
for _, row in amd_df.iterrows():
    model = extract_cpu_model(row["clean_product_name"])
    if model:
        amd_model_to_family[model] = row["product_family"]

amd_model_token_to_family = {}
for _, row in amd_df.iterrows():
    for token in extract_model_tokens(row["clean_product_name"]):
        if not is_socket_token(token):
            amd_model_token_to_family[token] = row["product_family"]


# ==================================================
# CLEAN GIGABYTE DATA
# ==================================================

gigabyte_df["clean_processor"] = gigabyte_df["processor"].apply(get_clean_processor_list)


# ==================================================
# MATCHING LOGIC
# ==================================================

def match_processors(processors):
    matched_names = []
    matched_families = []
    matched_lines = []

    for p in processors:
        clean_p = clean_processor_name(p)

        # ---------- INTEL ----------
        if clean_p in intel_name_to_family:
            matched_names.append(clean_p)
            matched_families.append(intel_name_to_family[clean_p])
            matched_lines.append(intel_name_to_line[clean_p])
            continue

        model = extract_cpu_model(clean_p)
        if model and model in intel_model_to_family:
            matched_names.append(model)
            matched_families.append(intel_model_to_family[model])
            matched_lines.append(intel_model_to_line[model])
            continue

        for token in extract_model_tokens(clean_p):
            if is_socket_token(token):
                continue
            if token in intel_model_token_to_family:
                matched_names.append(token)
                matched_families.append(intel_model_token_to_family[token])
                matched_lines.append(intel_model_token_to_line[token])
                break

        # ---------- AMD ----------
        if clean_p in amd_name_to_family:
            matched_names.append(clean_p)
            matched_families.append(amd_name_to_family[clean_p])
            matched_lines.append(None)
            continue

        if model and model in amd_model_to_family:
            matched_names.append(model)
            matched_families.append(amd_model_to_family[model])
            matched_lines.append(None)
            continue

        for token in extract_model_tokens(clean_p):
            if is_socket_token(token):
                continue
            if token in amd_model_token_to_family:
                matched_names.append(token)
                matched_families.append(amd_model_token_to_family[token])
                matched_lines.append(None)
                break

    return (
        clean_list(matched_names),
        clean_list(matched_families),
        clean_list(matched_lines),
    )


(
    gigabyte_df["mapped_product_name"],
    gigabyte_df["mapped_product_family"],
    gigabyte_df["mapped_product_line"],
) = zip(*gigabyte_df["clean_processor"].apply(match_processors))

# ==================================================
# STATUS LOGIC (compare with Gigabyte processor_family)
# ==================================================

import ast

def get_status(row):
    mapped = {
        normalize_family(f)
        for f in (row["mapped_product_family"] or [])
        if f
    }

    giga_raw = row["processor_family"]

    # ---- normalize processor_family ----
    if isinstance(giga_raw, float) and np.isnan(giga_raw):
        giga_list = []

    elif isinstance(giga_raw, str):
        # try to parse stringified list: "['epyc']"
        try:
            parsed = ast.literal_eval(giga_raw)
            giga_list = parsed if isinstance(parsed, list) else [parsed]
        except:
            giga_list = [giga_raw]

    elif isinstance(giga_raw, (list, tuple, set)):
        giga_list = giga_raw

    else:
        giga_list = [giga_raw]

    giga = {
        normalize_family(f)
        for f in giga_list
        if f
    }

    print(giga, "WWWWWWWWW")
    print(mapped, "QQQQQQQQQ")

    if not mapped:
        return "Family is not found"
    if not mapped.intersection(giga):
        return "mismatch"
    if not giga.issubset(mapped):
        return f"{len(giga - mapped)} family missing"
    return "match"

gigabyte_df["status"] = gigabyte_df.apply(get_status, axis=1)
# ==================================================
# SAVE OUTPUT
# ==================================================

gigabyte_df.to_csv("mapped_intel_amd_matched_output.csv", index=False)
print("Saved mapped_intel_amd_matched_output.csv")
