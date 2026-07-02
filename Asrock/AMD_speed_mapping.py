import pandas as pd
import re
import ast
from collections import Counter

# ==================================================
# CLEAN PROCESSOR NAME
# ==================================================

def clean_processor_name(name):

    if pd.isna(name):
        return ""

    name = str(name).lower()
    name = name.replace("®", "").replace("™", "")
    name = re.sub(r"\s+", " ", name)

    # Normalize AMD noise words
    name = name.replace("processor", "")
    name = name.replace("with radeon graphics", "")
    name = name.replace("series", "")

    return name.strip()


# ==================================================
# EXTRACT SPEED VALUES
# ==================================================

def extract_speed_values(text):

    if text is None:
        return []

    pattern = r"\d{4,5}\s*(?:MT/s|MHz)"
    matches = re.findall(pattern, str(text), re.IGNORECASE)

    cleaned = [re.sub(r"\s+", " ", m.strip()) for m in matches]

    return list(set(cleaned))


# ==================================================
# GET CLEAN PROCESSOR LIST (ASROCK)
# ==================================================

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
# LOAD FILES
# ==================================================

print("Loading files...")

asrock_df = pd.read_csv("02032026_asrock_db_import (1).csv", low_memory=False)
amd_df = pd.read_csv("09022026_amd_db_import (1).csv", low_memory=False)


# ==================================================
# CLEAN AMD PRODUCT NAMES
# ==================================================

amd_df["clean_product_name"] = amd_df["product_name"].apply(clean_processor_name)


# ==================================================
# CREATE AMD LOOKUP
# ==================================================

amd_lookup = dict(
    zip(amd_df["clean_product_name"], amd_df["maximum_memory_speed"])
)


# ==================================================
# CLEAN ASROCK PROCESSOR COLUMN
# ==================================================

asrock_df["clean_processor"] = asrock_df["processor"].apply(get_clean_processor_list)


# ==================================================
# MAP AMD MEMORY SPEED
# ==================================================

def map_max_memory_speed(processors):

    mapped = []

    for p in processors:

        for amd_name, speed_text in amd_lookup.items():

            # Flexible matching
            if p in amd_name or amd_name in p:

                speeds = extract_speed_values(speed_text)

                for s in speeds:
                    mapped.append(f"{amd_name} ({s})")

    return list(set(mapped))


asrock_df["mapped_maximum_memory_speed"] = asrock_df["clean_processor"].apply(
    map_max_memory_speed
)


# ==================================================
# EXTRACT PROCESSOR FROM STRING (VALIDATION)
# ==================================================

def extract_processor(text):

    text = clean_processor_name(text)

    # Extract AMD-like phrase
    m = re.search(r"(amd\s+[a-z0-9\s\-]+?)\s*\(", text)

    if m:
        return m.group(1).strip()

    return ""


# ==================================================
# MEMORY SPEED VALIDATION
# ==================================================

def memory_speed_validation(row):

    status = []

    duplicate_list = []
    empty_speed_list = []
    invalid_format = []
    processor_mismatch_list = []
    missing_speed = []
    extra_speed = []

    # --------------------------------------------
    # PARSE ASROCK DATA
    # --------------------------------------------

    try:
        items = ast.literal_eval(row["processor_max_memory_speed"])

        if not isinstance(items, list):
            items = [items]

    except:
        items = [row["processor_max_memory_speed"]]

    # --------------------------------------------
    # DUPLICATE CHECK
    # --------------------------------------------

    counts = Counter(items)
    duplicate_list = [item for item, count in counts.items() if count > 1]

    if duplicate_list:
        status.append("duplicate")

    # --------------------------------------------
    # INVALID FORMAT CHECK (RELAXED FOR AMD)
    # --------------------------------------------

    for item in items:

        if not re.search(r"\(\s*\d{4,5}\s*(?:MT/s|MHz)\s*\)$", str(item), re.IGNORECASE):
            invalid_format.append(item)

    if invalid_format:
        status.append("invalid_format")

    # --------------------------------------------
    # EMPTY SPEED CHECK
    # --------------------------------------------

    for item in items:

        if re.search(r"\(\s*\)", str(item)):
            empty_speed_list.append(item)

    if empty_speed_list:
        status.append("empty_speed")

    # --------------------------------------------
    # PROCESSOR MATCH CHECK
    # --------------------------------------------

    processors = set(row["clean_processor"])
    correct_count = 0

    for item in items:

        cpu = extract_processor(item)

        if cpu not in processors:
            processor_mismatch_list.append(item)
        else:
            correct_count += 1

    if processor_mismatch_list:
        status.append("processor_mismatch")

    # --------------------------------------------
    # SPEED COMPARISON
    # --------------------------------------------

    intel_speeds = set()

    for m in row["mapped_maximum_memory_speed"]:
        intel_speeds |= set(extract_speed_values(m))

    asrock_speeds = set()

    for item in items:
        asrock_speeds |= set(extract_speed_values(item))

    missing_speed = list(intel_speeds - asrock_speeds)
    extra_speed = list(asrock_speeds - intel_speeds)

    if missing_speed:
        status.append("missing")

    if extra_speed:
        status.append("mismatch")

    # --------------------------------------------
    # MATCH CHECK
    # --------------------------------------------

    if (
        correct_count > 0
        and not missing_speed
        and not extra_speed
        and not empty_speed_list
    ):
        status.append("match")

    # --------------------------------------------
    # FINAL STATUS
    # --------------------------------------------

    final_status = " & ".join(sorted(set(status)))

    return [
        final_status,
        ", ".join(duplicate_list),
        ", ".join(empty_speed_list),
        ", ".join(invalid_format),
        ", ".join(processor_mismatch_list),
        ", ".join(missing_speed),
        ", ".join(extra_speed)
    ]


# ==================================================
# APPLY VALIDATION
# ==================================================

asrock_df[
[
    "memory_speed_status",
    "duplicate_processor",
    "empty_speed_processor",
    "invalid_format_processor",
    "processor_mismatch",
    "missing_speed_from_asrock",
    "extra_speed_in_asrock"
]
] = asrock_df.apply(memory_speed_validation, axis=1, result_type="expand")


# ==================================================
# OUTPUT COLUMNS
# ==================================================

output_columns = [
    "server_description",
    "processor",
    "processor_max_memory_speed",
    "clean_processor",
    "mapped_maximum_memory_speed",
    "memory_speed_status",
    "duplicate_processor",
    "empty_speed_processor",
    "invalid_format_processor",
    "processor_mismatch",
    "missing_speed_from_asrock",
    "extra_speed_in_asrock"
]

output_df = asrock_df[output_columns].copy()


# ==================================================
# FORMAT LIST COLUMNS
# ==================================================

for col in ["clean_processor", "mapped_maximum_memory_speed"]:

    output_df[col] = output_df[col].apply(
        lambda x: ", ".join(x) if isinstance(x, list) else x
    )


# ==================================================
# SAVE OUTPUT
# ==================================================

output_df.to_csv("asrock_amd_memory_speed.csv", index=False)

print("✅ Validation completed.")
print("📁 File saved: asrock_amd_memory_speed.csv")