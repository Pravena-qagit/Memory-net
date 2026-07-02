# import pandas as pd
# import re
# import ast

# # ==============================
# # Load CSVs
# # ==============================
# supermicro_df = pd.read_csv("supermicro.csv")
# intel_df = pd.read_csv("12022026_intel_db_import.csv")
# amd_df = pd.read_csv("09022026_amd_db_import (1).csv")

# # ==============================
# # Cleaning Functions
# # ==============================
# def clean_text(text):
#     text = str(text).lower()
#     text = re.sub(r"[®™]", "", text)
#     text = re.sub(r"\bprocessors\b", "processor", text)
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def normalize_speed(speed):
#     return str(speed).strip().lower()


# def safe_list(val):
#     try:
#         return ast.literal_eval(val)
#     except:
#         return []


# # ==============================
# # Extract CPU Model
# # ==============================
# def extract_model(text):
#     text = clean_text(text)

#     # patterns = [
#     #     r"\b[a-z]\d{4}[a-z0-9]*\b",     # C2358, C5335C1, x7433FE
#     #     r"\b[a-z]\d-[a-z]?\d{4}\b",     # x7-Z8700
#     #     r"\be\d-\d+\s*v\d\b",           # E5-2600 v4
#     #     r"\bepyc\s*\d{4}\b",            # EPYC 7742
#     #     r"\b\d{4,5}[a-z]*\b"
#     # ]

#     patterns = [
#         r"\b[a-z]\d{4}[a-z0-9]*\b",
#         r"\b[a-z]\d-[a-z]?\d{4}\b",
#         r"\be\d-\d+\s*v\d\b",
#         r"\bepyc\s*\d{4}\b",
#         r"\b\d{4,5}[a-z]*\b"
#     ]

#     for pattern in patterns:
#         match = re.search(pattern, text)
#         if match:
#             return match.group()

#     return None


# # ==============================
# # Extract Processor Family
# # ==============================
# def extract_family(text):
#     text = clean_text(text)

#     keywords = [
#         "atom",
#         "xeon",
#         "epyc",
#         "gold",
#         "silver",
#         "platinum"
#     ]

#     for word in keywords:
#         if word in text:
#             return word

#     return None


# # ==============================
# # Build Lookup
# # ==============================
# model_speed_map = {}
# model_family_map = {}

# def build_lookup(df, is_amd=False):
#     for _, row in df.iterrows():
#         speed = normalize_speed(row.get("maximum_memory_speed", ""))

#         names = []

#         if not is_amd:
#             names.append(row.get("product_name", ""))
#         else:
#             names.append(row.get("product_name", ""))
#             names.append(row.get("processor_series", ""))

#         for name in names:
#             name_clean = clean_text(name)
#             model = extract_model(name_clean)
#             family = extract_family(name_clean)

#             if model:
#                 model_speed_map[model] = speed
#                 model_family_map[model] = family


# build_lookup(intel_df, is_amd=False)
# build_lookup(amd_df, is_amd=True)


# # ==============================
# # Matching Function
# # ==============================
# def get_processor_info(proc):
#     model = extract_model(proc)
#     family = extract_family(proc)

#     if model and model in model_speed_map:
#         return model_speed_map[model], model_family_map.get(model), family

#     return None, None, family


# # ==============================
# # Generate Expected Values
# # ==============================
# # def generate_expected(processor_list):
# #     expected = []
# #     missing = []
# #     family_mismatch = []

# #     for proc in processor_list:
# #         speed, correct_family, input_family = get_processor_info(proc)

# #         if speed:
# #             formatted = f"{proc} ({speed})"
# #             expected.append(clean_text(formatted))

# #             # Family mismatch detection
# #             if correct_family and input_family and correct_family != input_family:
# #                 family_mismatch.append(proc)

# #         else:
# #             missing.append(proc)

# #     return expected, missing, family_mismatch


# def generate_expected(processor_list):
#     expected = []
#     missing = []
#     missing_speed = []

#     for proc in processor_list:
#         model = extract_model(proc)

#         if model in model_speed_map:
#             speed = model_speed_map[model]

#             if speed:
#                 formatted = f"{proc} ({speed})"
#                 expected.append(clean_text(formatted))
#             else:
#                 missing_speed.append(proc)
#         else:
#             missing.append(proc)

#     return expected, missing, missing_speed

# # ==============================
# # Comparison Logic
# # ==============================
# def compare_row(row):
#     processor_list = safe_list(row.get("processor", ""))
#     actual_list = safe_list(row.get("processor_max_memory_speed", ""))

#     actual_clean = [clean_text(x) for x in actual_list]

#     expected_list, missing_processors, family_mismatch = generate_expected(processor_list)

#     # =====================
#     # Status Logic
#     # =====================
#     if not processor_list:
#         status = "missing_processor"

#     elif missing_processors:
#         status = "partial_match"

#     else:
#         matches = [e for e in expected_list if e in actual_clean]

#         if len(matches) == len(expected_list):
#             if family_mismatch:
#                 status = "mismatch"   # wrong branding like Atom vs Gold
#             else:
#                 status = "match"
#         elif matches:
#             status = "partial_match"
#         else:
#             status = "mismatch"

#     return pd.Series({
#         "status": status,
#         "expected_values": expected_list,
#         "actual_values": actual_clean,
#         "missing_processors": missing_processors
#     })


# # ==============================
# # Apply Logic
# # ==============================
# result_df = supermicro_df.copy()

# result_df[[
#     "status",
#     "expected_values",
#     "actual_values",
#     "missing_processors"
# ]] = result_df.apply(compare_row, axis=1)

# # ==============================
# # Select Required Columns
# # ==============================
# required_columns = [
#     "server_description",
#     "processor",
#     "processor_family",
#     "processor_line",
#     "processor_max_memory_speed",
#     "status",
#     "expected_values",
#     "actual_values",
#     "missing_processors"
# ]

# final_columns = [col for col in required_columns if col in result_df.columns]
# final_df = result_df[final_columns]


# # ==============================
# # Save Output
# # ==============================
# final_df.to_csv("final_validation_output.csv", index=False)

# print("✅ Final validation completed successfully!")















# import pandas as pd
# import re
# import ast

# # ==============================
# # Load CSVs
# # ==============================
# supermicro_df = pd.read_csv("supermicro.csv")
# intel_df = pd.read_csv("12022026_intel_db_import.csv")
# amd_df = pd.read_csv("09022026_amd_db_import (1).csv")

# # ==============================
# # Cleaning Functions
# # ==============================
# def clean_text(text):
#     text = str(text).lower()
#     text = re.sub(r"[®™]", "", text)
#     text = re.sub(r"\bprocessors\b", "processor", text)
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def normalize_speed(speed):
#     return str(speed).strip().lower()


# def safe_list(val):
#     try:
#         return ast.literal_eval(val)
#     except:
#         return []


# # ==============================
# # Extract CPU Model (FIXED)
# # ==============================
# def extract_model(text):
#     text = clean_text(text)

#     patterns = [
#         r"\b\d{2}[a-z]\d\b",            # 75F3, 73F3 ✅
#         r"\b[a-z]\d{4}[a-z0-9]*\b",     # C2358, C5335C1
#         r"\b[a-z]\d-[a-z]?\d{4}\b",     # x7-Z8700
#         r"\be\d-\d+\s*v\d\b",           # E5-2600 v4
#         r"\bepyc\s*\d{4}\b",            # EPYC 7742
#         r"\b\d{4,5}[a-z]*\b"
#     ]

#     for pattern in patterns:
#         match = re.search(pattern, text)
#         if match:
#             return match.group()

#     return None


# # ==============================
# # Extract Processor Family
# # ==============================
# def extract_family(text):
#     text = clean_text(text)

#     keywords = [
#         "atom",
#         "xeon",
#         "epyc",
#         "gold",
#         "silver",
#         "platinum"
#     ]

#     for word in keywords:
#         if word in text:
#             return word

#     return None


# # ==============================
# # Build Lookup (FIXED - NO OVERWRITE)
# # ==============================
# model_speed_map = {}
# model_family_map = {}

# def build_lookup(df, is_amd=False):
#     for _, row in df.iterrows():
#         speed = normalize_speed(row.get("maximum_memory_speed", ""))

#         names = []

#         if not is_amd:
#             names.append(row.get("product_name", ""))
#         else:
#             names.append(row.get("product_name", ""))
#             names.append(row.get("processor_series", ""))

#         for name in names:
#             name_clean = clean_text(name)
#             model = extract_model(name_clean)
#             family = extract_family(name_clean)

#             if model:
#                 # 🔥 KEY FIX: prevent overwrite with empty speed
#                 if model not in model_speed_map or (speed and not model_speed_map.get(model)):
#                     if speed:  # only store valid speed
#                         model_speed_map[model] = speed
#                         model_family_map[model] = family


# build_lookup(intel_df, is_amd=False)
# build_lookup(amd_df, is_amd=True)


# # ==============================
# # Matching Function
# # ==============================
# def get_processor_info(proc):
#     model = extract_model(proc)
#     family = extract_family(proc)

#     if model and model in model_speed_map:
#         return model_speed_map[model], model_family_map.get(model), family

#     return None, None, family


# # ==============================
# # Generate Expected Values
# # ==============================
# def generate_expected(processor_list):
#     expected = []
#     missing = []
#     family_mismatch = []

#     for proc in processor_list:
#         speed, correct_family, input_family = get_processor_info(proc)

#         if speed:
#             formatted = f"{proc} ({speed})"
#             expected.append(clean_text(formatted))

#             # Detect wrong branding (Atom vs Gold)
#             if correct_family and input_family and correct_family != input_family:
#                 family_mismatch.append(proc)

#         else:
#             missing.append(proc)

#     return expected, missing, family_mismatch


# # ==============================
# # Comparison Logic
# # ==============================
# def compare_row(row):
#     processor_list = safe_list(row.get("processor", ""))
#     actual_list = safe_list(row.get("processor_max_memory_speed", ""))

#     actual_clean = [clean_text(x) for x in actual_list]

#     expected_list, missing_processors, family_mismatch = generate_expected(processor_list)

#     if not processor_list:
#         status = "missing_processor"

#     elif missing_processors:
#         status = "partial_match"

#     else:
#         matches = [e for e in expected_list if e in actual_clean]

#         if len(matches) == len(expected_list):
#             if family_mismatch:
#                 status = "mismatch"
#             else:
#                 status = "match"
#         elif matches:
#             status = "partial_match"
#         else:
#             status = "mismatch"

#     return pd.Series({
#         "status": status,
#         "expected_values": expected_list,
#         "actual_values": actual_clean,
#         "missing_processors": missing_processors
#     })


# # ==============================
# # Apply Logic
# # ==============================
# result_df = supermicro_df.copy()

# result_df[[
#     "status",
#     "expected_values",
#     "actual_values",
#     "missing_processors"
# ]] = result_df.apply(compare_row, axis=1)


# # ==============================
# # Select Required Columns
# # ==============================
# required_columns = [
#     "server_description",
#     "processor",
#     "processor_family",
#     "processor_line",
#     "processor_max_memory_speed",
#     "status",
#     "expected_values",
#     "actual_values",
#     "missing_processors"
# ]

# final_columns = [col for col in required_columns if col in result_df.columns]
# final_df = result_df[final_columns]


# # ==============================
# # Save Output
# # ==============================
# final_df.to_csv("final_validation_output.csv", index=False)

# print("✅ Final validation completed successfully!")











# import pandas as pd
# import re
# import ast

# # ==============================
# # Load CSVs
# # ==============================
# supermicro_df = pd.read_csv("supermicro.csv")
# intel_df = pd.read_csv("12022026_intel_db_import.csv")
# amd_df = pd.read_csv("09022026_amd_db_import (1).csv")

# # ==============================
# # Cleaning Functions
# # ==============================
# def clean_text(text):
#     text = str(text).lower()
#     text = re.sub(r"[®™]", "", text)
#     text = re.sub(r"\bprocessors\b", "processor", text)
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def normalize_speed(speed):
#     return str(speed).strip().lower()


# def safe_list(val):
#     try:
#         return ast.literal_eval(val)
#     except:
#         return []


# # ==============================
# # Extract CPU Model
# # ==============================
# def extract_model(text):
#     text = clean_text(text)

#     patterns = [
#         r"\b\d{2}[a-z]\d\b",            # 75F3, 73F3
#         r"\b[a-z]\d{4}[a-z0-9]*\b",     # C2358, C5335C1
#         r"\b[a-z]\d-[a-z]?\d{4}\b",     # x7-Z8700
#         r"\be\d-\d+\s*v\d\b",           # E5-2600 v4
#         r"\bepyc\s*\d{4}\b",            # EPYC 7742
#         r"\b\d{4,5}[a-z]*\b"
#     ]

#     for pattern in patterns:
#         match = re.search(pattern, text)
#         if match:
#             return match.group()

#     return None


# # ==============================
# # Extract Processor Family
# # ==============================
# def extract_family(text):
#     text = clean_text(text)

#     keywords = ["atom", "xeon", "epyc", "gold", "silver", "platinum"]

#     for word in keywords:
#         if word in text:
#             return word

#     return None


# # ==============================
# # Detect Series Processors
# # ==============================
# # def is_series_processor(text):
# #     text = clean_text(text)
# #     return bool(re.search(r"\b\d{4}\s*series\b", text))

# # def is_series_processor(text):
# #     text = clean_text(text)

# #     patterns = [
# #         r"\b\d{4}\s*series\b",        # 7001 Series
# #         r"\b\d{4}\s*processor\b",     # 7001 Processor
# #         r"\b\d{4}\s*processors\b",    # 7001 Processors ✅ NEW
# #     ]

# #     for pattern in patterns:
# #         if re.search(pattern, text):
# #             return True

# #     return False

# def is_series_processor(text):
#     text = clean_text(text)

#     # Skip EPYC series patterns like 7001, 7002, 9004 etc.
#     if "epyc" in text:
#         if re.search(r"\b\d{4}\s*(series|processor|processors)\b", text):
#             # Ensure it's NOT like 75F3
#             if not re.search(r"\b\d{2}[a-z]\d\b", text):
#                 return True

#     return False

# # ==============================
# # Build Lookup (NO OVERWRITE BUG)
# # ==============================
# model_speed_map = {}
# model_family_map = {}

# def build_lookup(df, is_amd=False):
#     for _, row in df.iterrows():
#         speed = normalize_speed(row.get("maximum_memory_speed", ""))

#         names = []

#         if not is_amd:
#             names.append(row.get("product_name", ""))
#         else:
#             names.append(row.get("product_name", ""))
#             names.append(row.get("processor_series", ""))

#         for name in names:
#             name_clean = clean_text(name)
#             model = extract_model(name_clean)
#             family = extract_family(name_clean)

#             if model:
#                 # ✅ Prevent overwrite with empty values
#                 if model not in model_speed_map or (speed and not model_speed_map.get(model)):
#                     if speed:
#                         model_speed_map[model] = speed
#                         model_family_map[model] = family


# build_lookup(intel_df, is_amd=False)
# build_lookup(amd_df, is_amd=True)


# # ==============================
# # Matching Function
# # ==============================
# def get_processor_info(proc):
#     model = extract_model(proc)
#     family = extract_family(proc)

#     if model and model in model_speed_map:
#         return model_speed_map[model], model_family_map.get(model), family

#     return None, None, family


# # ==============================
# # Generate Expected Values
# # ==============================
# def generate_expected(processor_list):
#     expected = []
#     missing = []
#     family_mismatch = []

#     for proc in processor_list:

#         # 🚫 Skip series processors
#         if is_series_processor(proc):
#             continue

#         speed, correct_family, input_family = get_processor_info(proc)

#         if speed:
#             formatted = f"{proc} ({speed})"
#             expected.append(clean_text(formatted))

#             # Detect wrong branding
#             if correct_family and input_family and correct_family != input_family:
#                 family_mismatch.append(proc)

#         else:
#             missing.append(proc)

#     return expected, missing, family_mismatch


# # ==============================
# # Comparison Logic
# # ==============================
# def compare_row(row):
#     processor_list = safe_list(row.get("processor", ""))
#     actual_list = safe_list(row.get("processor_max_memory_speed", ""))

#     actual_clean = [clean_text(x) for x in actual_list]

#     expected_list, missing_processors, family_mismatch = generate_expected(processor_list)

#     # =====================
#     # Status Logic
#     # =====================
#     if not processor_list:
#         status = "missing_processor"

#     elif not expected_list and not missing_processors:
#         status = "skipped_series"

#     elif missing_processors:
#         status = "partial_match"

#     else:
#         matches = [e for e in expected_list if e in actual_clean]

#         if len(matches) == len(expected_list):
#             if family_mismatch:
#                 status = "mismatch"
#             else:
#                 status = "match"
#         elif matches:
#             status = "partial_match"
#         else:
#             status = "mismatch"

#     return pd.Series({
#         "status": status,
#         "expected_values": expected_list,
#         "actual_values": actual_clean,
#         "missing_processors": missing_processors
#     })


# # ==============================
# # Apply Logic
# # ==============================
# result_df = supermicro_df.copy()

# result_df[[
#     "status",
#     "expected_values",
#     "actual_values",
#     "missing_processors"
# ]] = result_df.apply(compare_row, axis=1)


# # ==============================
# # Select Required Columns
# # ==============================
# required_columns = [
#     "server_description",
#     "processor",
#     "processor_family",
#     "processor_line",
#     "processor_max_memory_speed",
#     "status",
#     "expected_values",
#     "actual_values",
#     "missing_processors"
# ]

# final_columns = [col for col in required_columns if col in result_df.columns]
# final_df = result_df[final_columns]


# # ==============================
# # Save Output
# # ==============================
# final_df.to_csv("final_validation_output.csv", index=False)

# print("✅ Final validation completed successfully!")









import pandas as pd
import re
import ast

# ==============================
# Load CSVs
# ==============================
supermicro_df = pd.read_csv("supermicro.csv")
intel_df = pd.read_csv("12022026_intel_db_import.csv")
amd_df = pd.read_csv("09022026_amd_db_import (1).csv")

# ==============================
# Cleaning Functions
# ==============================
def clean_text(text):
    text = str(text).lower()
    text = re.sub(r"[®™]", "", text)
    text = re.sub(r"\bprocessors\b", "processor", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_speed(speed):
    return str(speed).strip().lower()


def safe_list(val):
    try:
        return ast.literal_eval(val)
    except:
        return []


# ==============================
# Extract CPU Model
# ==============================
def extract_model(text):
    text = clean_text(text)

    patterns = [
        r"\b\d{2}[a-z]\d\b",            # 75F3
        r"\b[a-z]\d{4}[a-z0-9]*\b",     # C2358, C5335C1
        r"\b[a-z]\d-[a-z]?\d{4}\b",     # x7-Z8700
        r"\be\d-\d+\s*v\d\b",           # E5-2600 v4
        r"\bepyc\s*\d{4}\b",            # EPYC 7742
        r"\b\d{4,5}[a-z]*\b",
        r"\b\d{4}[a-z0-9]+\b"           # 5500X3D
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group()

    return None


# ==============================
# Extract Processor Family
# ==============================
def extract_family(text):
    text = clean_text(text)

    keywords = ["atom", "xeon", "epyc", "ryzen", "gold", "silver", "platinum"]

    for word in keywords:
        if word in text:
            return word

    return None


# ==============================
# Skip EPYC Series
# ==============================
def is_series_processor(text):
    text = clean_text(text)

    if "epyc" in text:
        if re.search(r"\b\d{4}\s*(series|processor|processors)\b", text):
            if not re.search(r"\b\d{2}[a-z]\d\b", text):  # avoid 75F3
                return True

    return False


# ==============================
# Build Lookup (NO OVERWRITE)
# ==============================
model_speed_map = {}
model_family_map = {}

def build_lookup(df, is_amd=False):
    for _, row in df.iterrows():
        speed = normalize_speed(row.get("maximum_memory_speed", ""))

        names = []

        if not is_amd:
            names.append(row.get("product_name", ""))
        else:
            names.append(row.get("product_name", ""))
            names.append(row.get("processor_series", ""))

        for name in names:
            name_clean = clean_text(name)
            model = extract_model(name_clean)
            family = extract_family(name_clean)

            if model:
                # prevent overwrite with empty
                if model not in model_speed_map or (speed and not model_speed_map.get(model)):
                    if speed:
                        model_speed_map[model] = speed
                        model_family_map[model] = family


build_lookup(intel_df, is_amd=False)
build_lookup(amd_df, is_amd=True)


# ==============================
# Get Processor Info
# ==============================
def get_processor_info(proc):
    model = extract_model(proc)
    family = extract_family(proc)

    if model and model in model_speed_map:
        return model_speed_map[model], model_family_map.get(model), family

    return None, None, family


# ==============================
# Generate Expected Values
# ==============================
def generate_expected(processor_list):
    expected = []
    missing = []
    family_mismatch = []

    for proc in processor_list:

        # 🚫 Skip series processors
        if is_series_processor(proc):
            continue

        model = extract_model(proc)

        # 🚫 Skip if not in DB
        if not model or model not in model_speed_map:
            continue

        speed, correct_family, input_family = get_processor_info(proc)

        if speed:
            formatted = f"{proc} ({speed})"
            expected.append(clean_text(formatted))

            if correct_family and input_family and correct_family != input_family:
                family_mismatch.append(proc)

        else:
            missing.append(proc)

    return expected, missing, family_mismatch


# ==============================
# Compare Row
# ==============================
# def compare_row(row):
#     processor_list = safe_list(row.get("processor", ""))
#     actual_list = safe_list(row.get("processor_max_memory_speed", ""))

#     actual_clean = [clean_text(x) for x in actual_list]

#     expected_list, missing_processors, family_mismatch = generate_expected(processor_list)

#     if not processor_list:
#         status = "missing_processor"

#     elif not expected_list:
#         status = "skipped_all"

#     elif expected_list and missing_processors:
#         status = "partial_match"

#     else:
#         matches = [e for e in expected_list if e in actual_clean]

#         if len(matches) == len(expected_list):
#             status = "match" if not family_mismatch else "mismatch"
#         elif matches:
#             status = "partial_match"
#         else:
#             status = "mismatch"

#     return pd.Series({
#         "status": status,
#         "expected_values": expected_list,
#         "actual_values": actual_clean,
#         "missing_processors": missing_processors
#     })


def compare_row(row):
    processor_list = safe_list(row.get("processor", ""))
    actual_list = safe_list(row.get("processor_max_memory_speed", ""))

    actual_clean = [clean_text(x) for x in actual_list]

    # 🔥 NEW: Clean original column also
    original_clean = [clean_text(x) for x in actual_list]

    expected_list, missing_processors, family_mismatch = generate_expected(processor_list)

    # =========================
    # 🔥 OVERRIDE RULE
    # =========================
    if actual_clean == original_clean:
        return pd.Series({
            "status": "match",
            "expected_values": expected_list,
            "actual_values": actual_clean,
            "missing_processors": missing_processors
        })

    # =========================
    # EXISTING LOGIC
    # =========================
    if not processor_list:
        status = "missing_processor"

    elif not expected_list:
        status = "skipped_all"

    elif expected_list and missing_processors:
        status = "partial_match"

    else:
        matches = [e for e in expected_list if e in actual_clean]

        if len(matches) == len(expected_list):
            status = "match" if not family_mismatch else "mismatch"
        elif matches:
            status = "partial_match"
        else:
            status = "mismatch"

    return pd.Series({
        "status": status,
        "expected_values": expected_list,
        "actual_values": actual_clean,
        "missing_processors": missing_processors
    })




# ==============================
# Apply
# ==============================
result_df = supermicro_df.copy()

result_df[[
    "status",
    "expected_values",
    "actual_values",
    "missing_processors"
]] = result_df.apply(compare_row, axis=1)


# ==============================
# Final Columns
# ==============================
required_columns = [
    "server_description",
    "processor",
    "processor_family",
    "processor_line",
    "processor_max_memory_speed",
    "status",
    "expected_values",
    "actual_values",
    "missing_processors"
]

final_df = result_df[[col for col in required_columns if col in result_df.columns]]


# ==============================
# Save Output
# ==============================
final_df.to_csv("final_validation_output.csv", index=False)

print("✅ Final validation completed successfully!")