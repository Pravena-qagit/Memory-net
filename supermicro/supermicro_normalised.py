import pandas as pd
import re

# ---------------- PRECOMPILE REGEX ----------------
CLEAN_TEXT_PATTERN = re.compile(r"[^\w\s\+\-]")
NOISE_WORDS_PATTERN = re.compile(r"\b(system|server)\b", re.IGNORECASE)

# ✅ FINAL ULTIMATE MODEL PATTERN
MODEL_PATTERN = re.compile(
    r"\b(?!\d+-[A-Za-z])(?:"
    r"[A-Z][A-Z0-9]*-[A-Z0-9][A-Za-z0-9\-\+_]*"   # E50-9AP-Wifi, SBI-8149P-C4N
    r"|"
    r"[0-9]{3,}[A-Za-z0-9]*-[A-Za-z0-9\-\+_]+"    # 5016Ti-TF
    r"|"
    r"[A-Z0-9_]{4,}"                             # X7DBE_
    r")\b"
)

PAREN_PATTERN = re.compile(r"\(.*?\)")
HYPHEN_FIX_PATTERN = re.compile(r"\b([A-Za-z0-9]+)\s*-\s*([A-Za-z0-9\-_]+)")


# ---------------- HELPERS ----------------
def normalize(text):
    text = "" if pd.isna(text) else str(text)
    text = CLEAN_TEXT_PATTERN.sub(" ", text)
    text = NOISE_WORDS_PATTERN.sub("", text)
    return " ".join(text.lower().split())


def normalize_models(text):
    if pd.isna(text) or not str(text).strip():
        return []

    parts = re.split(r"[,/]", str(text))
    parts = [
        re.sub(r"[^\w\+_]", "", p).lower().strip()
        for p in parts if p.strip()
    ]
    return sorted(parts)


def split_supermicro(desc):
    desc = "" if pd.isna(desc) else str(desc).strip()

    desc_clean = PAREN_PATTERN.sub("", desc)
    desc_clean = HYPHEN_FIX_PATTERN.sub(r"\1-\2", desc_clean)

    match = MODEL_PATTERN.search(desc_clean)

    if not match:
        return desc_clean.strip(), ""

    family = desc_clean[:match.start()]
    model_part = desc_clean[match.start():]

    family = CLEAN_TEXT_PATTERN.sub(" ", family)
    family = " ".join(family.split())
    model_part = " ".join(model_part.split())

    return family, model_part


def has_internal_duplicates(text):
    if pd.isna(text) or not str(text).strip():
        return False

    parts = [normalize(x) for x in str(text).split(",")]
    return len(parts) != len(set(parts))


# ---------------- LOAD ----------------
df = pd.read_csv("supermicro_normalised_hosts.csv")

# ---------------- PREPROCESS ----------------
df["server_description"] = df["server_description"].fillna("").astype(str).str.strip()
df["actual_B"] = df["B"].fillna("").astype(str).str.strip()
df["actual_C"] = df["C"].fillna("").astype(str).str.strip()

# ---------------- VECTORIZED SPLIT ----------------
split_results = df["server_description"].apply(split_supermicro)
df["extracted_B"] = split_results.str[0]
df["extracted_C"] = split_results.str[1]

# ---------------- STATUS LOGIC ----------------
df["status"] = "MATCH"

# Missing
missing_mask = (df["actual_B"] == "") | (df["actual_C"] == "")
df.loc[missing_mask, "status"] = "MISSING"

# Duplicate in cell
dup_cell_mask = df["actual_B"].apply(has_internal_duplicates)
df.loc[dup_cell_mask, "status"] = "DUPLICATE_IN_CELL"

# ✅ FIXED mismatch logic
mismatch_mask = (
    (df["status"] == "MATCH") &
    (
        (df["actual_B"].apply(normalize) != df["extracted_B"].apply(normalize)) |
        (df["actual_C"].apply(normalize_models) != df["extracted_C"].apply(normalize_models))
    )
)
df.loc[mismatch_mask, "status"] = "MISMATCH"

# ---------------- ROW DUPLICATES ----------------
duplicate_mask = (
    df.duplicated(subset=["actual_B", "actual_C"], keep="first")
    & (df["actual_B"] != "")
    & (df["actual_C"] != "")
)

df.loc[
    duplicate_mask & (df["status"] == "MATCH"),
    "status"
] = "DUPLICATE"

# ---------------- OUTPUT ----------------
df.to_csv("supermicro_normalization_report.csv", index=False)

print(df["status"].value_counts())