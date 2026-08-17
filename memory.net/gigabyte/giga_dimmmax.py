import pandas as pd
import json
import re

# Load CSV
df = pd.read_csv("updated_gigabyte_file1.csv")

# Convert written numbers to digits
def word_to_number(text):
    units = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9
    }
    teens = {
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19
    }
    tens = {
        "twenty": 20, "thirty": 30, "forty": 40,
        "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90
    }

    text = text.lower().replace('-', ' ')
    parts = text.split()
    total = 0

    if len(parts) == 1:
        if parts[0] in units:
            total = units[parts[0]]
        elif parts[0] in teens:
            total = teens[parts[0]]
        elif parts[0] in tens:
            total = tens[parts[0]]
    elif len(parts) == 2:
        if parts[0] in tens and parts[1] in units:
            total = tens[parts[0]] + units[parts[1]]

    return str(total) if total > 0 else None

# Extract DIMM slot count from string or list
def extract_dimm_slots(text):
    if isinstance(text, list):
        text = " ".join(text)
    text = text.lower()

    # IMPORTANT: Keep DDR2 DIMM info to allow extraction, so COMMENT OUT below line
    # if "ddr2" in text:
    #     text = re.sub(r"\d+\s*x\s*\d+\.\d+v\s*ddr2.*?(socket|slot)?", "", text)

    total_match = re.search(r"total[:\s]*([\d]+)\s*x\s*dimm", text)
    if total_match:
        return total_match.group(1)

    match = re.search(r"(\d+)\s*x\s*[\w\.\s\-]*dimm", text)
    if match:
        return match.group(1)

    all_matches = re.findall(r"(\d+)\s*(?:x\s*)?(?:[\w\-]*)\s*dimm[s]?\s*(slots?|sockets?)?", text)
    if all_matches:
        numbers = [int(m) for m in all_matches]
        return str(max(numbers)) if numbers else None

    match_word = re.search(r"\b([a-z\-]+)\b.*?dimm", text)
    if match_word:
        return word_to_number(match_word.group(1))

    return None

# Extract memory capacity and DIMM sizes
def extract_memory_fields(spec):
    try:
        data = json.loads(spec)
        extracted_dimm_slots = None
        memory_sizes = []

        def extract_from_list(items):
            nonlocal extracted_dimm_slots, memory_sizes
            for item in items:
                if not isinstance(item, str):
                    continue
                item_lower = item.lower()
                if "bandwidth" in item_lower:
                    continue
                if not extracted_dimm_slots:
                    extracted_dimm_slots = extract_dimm_slots(items)

                # Remove content inside parentheses to ignore single DIMM sizes
                item_no_paren = re.sub(r"\([^)]*\)", "", item)

                # Extract normal GB/TB values
                size_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(GB|TB)", item_no_paren, re.IGNORECASE)
                for val, unit in size_matches:
                    val = float(val)
                    unit = unit.upper()
                    if unit == "TB":
                        memory_sizes.append(val * 1024)
                    elif unit == "GB":
                        memory_sizes.append(val)

                # Look for 'modules up to XXGB supported' pattern to extract max module sizes
                module_size_matches = re.findall(r"modules up to (\d+(?:\.\d+)?)\s*GB supported", item_no_paren, re.IGNORECASE)
                for val in module_size_matches:
                    val = float(val)
                    memory_sizes.append(val)

        keys_to_check = [
            "Memory", "System Memory", "Memory Capacity",
            "Memory Type", "DIMM Sizes", "System Memory (per Node)"
        ]

        for key in keys_to_check:
            section = data.get(key)
            if isinstance(section, dict):
                for val in section.values():
                    extract_from_list(val if isinstance(val, list) else [val])
            elif isinstance(section, list):
                extract_from_list(section)
            elif isinstance(section, str):
                extract_from_list([section])

        wrapped_capacity = [str(extracted_dimm_slots)] if extracted_dimm_slots else None

        if memory_sizes:
            max_size = max(memory_sizes)
            wrapped_dimm_size = [f"{int(max_size) if max_size.is_integer() else max_size}GB"]
        else:
            wrapped_dimm_size = None

        return pd.Series({
            "Memory Capacity": wrapped_capacity,
            "DIMM Sizes": wrapped_dimm_size
        })

    except Exception:
        return pd.Series({"Memory Capacity": None, "DIMM Sizes": None})

# Apply extraction
memory_df = df["server_specification"].apply(extract_memory_fields)
memory_df["server_description"] = df["server_description"]
memory_df["server_specification"] = df["server_specification"]
memory_df["host_url"] = df["host_url"]
memory_df["dimm_slots"] = df["dimm_slots"]
memory_df["maximum_memory"] = df["maximum_memory"]

final_df = memory_df[[
    "server_description", "server_specification", "host_url",
    "dimm_slots", "maximum_memory", "Memory Capacity", "DIMM Sizes"
]].copy()

# Enforce list format for Memory Capacity column values
final_df["Memory Capacity"] = final_df["Memory Capacity"].apply(
    lambda x: x if isinstance(x, list) else ([str(x)] if pd.notna(x) else None)
)

# Match check for DIMM slots
def check_dimm_slot_match(row):
    try:
        if str(row["server_specification"]).strip() == "{}":
            return "Datas are not available"

        dimm_slots_val = row["dimm_slots"]
        if isinstance(dimm_slots_val, list):
            dimm_slots_val = dimm_slots_val[0] if dimm_slots_val else None

        slot_num = None
        if pd.notna(dimm_slots_val):
            match = re.search(r"\d+", str(dimm_slots_val))
            if match:
                slot_num = match.group(0)

        memory_capacity_val = (
            row["Memory Capacity"][0] if isinstance(row["Memory Capacity"], list) and row["Memory Capacity"]
            else None
        )

        if not slot_num or memory_capacity_val is None:
            return "missing"

        return "match" if str(slot_num).strip() == str(memory_capacity_val).strip() else "mismatch"

    except:
        return "error"

# Match check for memory size divisibility
def check_memory_size_match(row):
    try:
        if str(row["server_specification"]).strip() == "{}":
            return "Datas are not available"
        if pd.isna(row["maximum_memory"]) or not row["DIMM Sizes"]:
            return "missing"

        max_mem_match = re.search(r"(\d+(?:\.\d+)?)", str(row["maximum_memory"]))
        dimm_size_val = row["DIMM Sizes"][0] if isinstance(row["DIMM Sizes"], list) and row["DIMM Sizes"] else None
        dimm_size_match = re.search(r"(\d+(?:\.\d+)?)", str(dimm_size_val))

        if max_mem_match and dimm_size_match:
            max_mem = float(max_mem_match.group(1))
            dimm_size = float(dimm_size_match.group(1))
            return "match" if max_mem % dimm_size == 0 else "mismatch"
        else:
            return "missing"
    except:
        return "error"

# Apply validations
final_df["dimm_slot_match"] = final_df.apply(check_dimm_slot_match, axis=1)
final_df["memory_size_match"] = final_df.apply(check_memory_size_match, axis=1)

# Save outputs
final_df.to_csv("gigabyte_memory_info.csv", index=False)
print("✅ Extracted and saved to 'gigabyte_memory_info.csv'")

problem_rows = final_df[
    final_df["dimm_slot_match"].isin(["mismatch", "missing", "Datas are not available"]) |
    final_df["memory_size_match"].isin(["mismatch", "missing", "Datas are not available"])
]
problem_rows.to_csv("problem_memory_rows(10).csv", index=False)
print("⚠️  Saved problematic rows to 'problem_memory_rows(10).csv'")
