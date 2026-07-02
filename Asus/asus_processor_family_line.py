import pandas as pd
import re
import numpy as np
import ast

# ==================================================
# HELPERS
# ==================================================

def ensure_list(x):
    """
    Convert values safely into list format.
    """
    if isinstance(x, list):
        return x

    if pd.isna(x):
        return []

    # Convert string representation of list into actual list
    if isinstance(x, str):
        x = x.strip()

        if x.startswith("[") and x.endswith("]"):
            try:
                parsed = ast.literal_eval(x)

                if isinstance(parsed, list):
                    return parsed

            except:
                pass

    return [x]


def clean_list(values):
    cleaned = []

    for v in values:

        if v is None:
            continue

        if isinstance(v, float) and np.isnan(v):
            continue

        if v not in cleaned:
            cleaned.append(v)

    return cleaned


# ==================================================
# CLEANING FUNCTIONS
# ==================================================

def clean_processor_name(name):
    """
    Normalize processor names.
    """

    name = str(name).lower()

    name = re.sub(r"\b\d+x\b", "", name)

    name = re.sub(r"\bdual\b|\bsingle\b", "", name)

    name = re.sub(r"\bgeneration\b", "gen", name)

    name = re.sub(r"\bprocessors\b", "processor", name)

    name = re.sub(
        r"\b(soc|quad-core|dual-core|single-core|i[- ]?series)\b",
        "",
        name
    )

    name = re.sub(r"[®™Â]", "", name)

    name = re.sub(r"[^\w\s-]", " ", name)

    name = re.sub(r"\s+", " ", name)

    return name.strip()


def get_clean_asus_processor_list(x):
    """
    Convert ASUS processor column into normalized list.
    """

    if pd.isna(x):
        return []

    x = str(x)

    try:
        proc_list = ast.literal_eval(x)

        if not isinstance(proc_list, list):
            proc_list = [proc_list]

    except:
        proc_list = [x]

    return [
        clean_processor_name(str(p).strip().strip('"').strip("'"))
        for p in proc_list
        if p and str(p).lower() not in ("nan", "none")
    ]


# ==================================================
# NORMALIZATION
# ==================================================

def normalize_family(text):
    """
    Normalize family/line names before comparison.
    """

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
# MATCHING FUNCTION
# ==================================================

def match_asus_processors_with_trace(processors):

    matched_names = []
    matched_families = []
    matched_lines = []

    trace = []

    unmatched = []

    for p in processors:

        fam = None
        line = None
        name = None

        # =========================
        # INTEL MATCH
        # =========================

        if p in intel_product_name_set:

            name = p

            fam = intel_name_to_family.get(p)

            line = intel_name_to_line.get(p)

        # =========================
        # AMD MATCH
        # =========================

        elif p in amd_product_name_set:

            name = p

            fam = amd_name_to_family.get(p)

            line = amd_name_to_line.get(p)

        else:
            unmatched.append(p)
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
        trace,
        clean_list(unmatched)
    )


# ==================================================
# STATUS CALCULATION
# ==================================================

def get_asus_status(row):

    mapped_fam = {
        normalize_family(f)
        for f in ensure_list(row["mapped_product_family"])
    }

    actual_fam = {
        normalize_family(f)
        for f in ensure_list(row["processor_family"])
    }

    mapped_line = {
        normalize_family(l)
        for l in ensure_list(row["mapped_product_line"])
    }

    actual_line = {
        normalize_family(l)
        for l in ensure_list(row["processor_line"])
    }

    # ==========================================
    # DIFFERENCE CALCULATION
    # ==========================================

    missing_fam = mapped_fam - actual_fam

    extra_fam = actual_fam - mapped_fam

    missing_line = mapped_line - actual_line

    extra_line = actual_line - mapped_line

    # ==========================================
    # STATUS MESSAGE
    # ==========================================

    def plural(word, count):
        return word if count == 1 else word + "s"

    messages = []

    if not mapped_fam and not mapped_line:

        status = "no match"

    else:

        if missing_fam:
            messages.append(
                f"{len(missing_fam)} "
                f"{plural('family', len(missing_fam))} missing"
            )

        if extra_fam:
            messages.append(
                f"{len(extra_fam)} "
                f"{plural('family', len(extra_fam))} mismatch"
            )

        if missing_line:
            messages.append(
                f"{len(missing_line)} "
                f"{plural('line', len(missing_line))} missing"
            )

        if extra_line:
            messages.append(
                f"{len(extra_line)} "
                f"{plural('line', len(extra_line))} mismatch"
            )

        status = "match" if not messages else " & ".join(messages)

    return pd.Series({
        "missing_family": sorted(list(missing_fam)),
        "missing_line": sorted(list(missing_line)),
        "status": status
    })


# ==================================================
# LOAD FILES
# ==================================================

asus_df = pd.read_csv(
    "29042026_asus_db_import.csv",
    low_memory=False
)

intel_df = pd.read_csv(
    "12022026_intel_db_import.csv",
    low_memory=False
)

amd_df = pd.read_csv(
    "09022026_amd_db_import.csv",
    low_memory=False
)


# ==================================================
# PREPARE ASUS DATA
# ==================================================

asus_df["clean_processor"] = (
    asus_df["processor"]
    .apply(get_clean_asus_processor_list)
)


# ==================================================
# PREPARE INTEL DATA
# ==================================================

intel_df["clean_product_name"] = (
    intel_df["product_name"]
    .apply(clean_processor_name)
)

intel_name_to_family = dict(
    zip(
        intel_df["clean_product_name"],
        intel_df["product_family"]
    )
)

intel_name_to_line = dict(
    zip(
        intel_df["clean_product_name"],
        intel_df["product_line"]
    )
)

intel_product_name_set = set(
    intel_name_to_family.keys()
)


# ==================================================
# PREPARE AMD DATA
# ==================================================

amd_df["clean_product_name"] = (
    amd_df["product_name"]
    .apply(clean_processor_name)
)

amd_name_to_family = dict(
    zip(
        amd_df["clean_product_name"],
        amd_df["product_family"]
    )
)

amd_name_to_line = dict(
    zip(
        amd_df["clean_product_name"],
        amd_df["processor_series"]
    )
)

amd_product_name_set = set(
    amd_name_to_family.keys()
)


# ==================================================
# MATCHING
# ==================================================

(
    asus_df["mapped_product_name"],
    asus_df["mapped_product_family"],
    asus_df["mapped_product_line"],
    asus_df["mapping_trace"],
    asus_df["unmapped_processor"]

) = zip(*asus_df["clean_processor"].apply(
    match_asus_processors_with_trace
))


# ==================================================
# STATUS + MISSING VALUES
# ==================================================

asus_df[
    ["missing_family", "missing_line", "status"]
] = asus_df.apply(
    get_asus_status,
    axis=1
)


# ==================================================
# OUTPUT COLUMNS
# ==================================================

output_columns = [
    "server_description",
    "processor",
    "processor_family",
    "processor_line",
    "clean_processor",
    "mapped_product_name",
    "mapped_product_family",
    "mapped_product_line",
    "missing_family",
    "missing_line",
    "unmapped_processor",
    "status"
]

output_df = asus_df[output_columns].copy()


# ==================================================
# CONVERT LISTS TO STRINGS
# ==================================================

list_columns = [
    "clean_processor",
    "mapped_product_name",
    "mapped_product_family",
    "mapped_product_line",
    "missing_family",
    "missing_line",
    "unmapped_processor"
]

for col in list_columns:

    output_df[col] = output_df[col].apply(
        lambda x: ", ".join(map(str, x))
        if isinstance(x, list)
        else str(x)
    )


# ==================================================
# SAVE OUTPUT
# ==================================================

output_file = "asus_processor_family_line_report.csv"

output_df.to_csv(
    output_file,
    index=False
)

print(f"Saved {output_file} 🚀")