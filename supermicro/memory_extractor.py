import pandas as pd
import json
import re

# Load CSV
df = pd.read_csv("formatted_host_specs (1).csv")

# Word to digit mappings
word_to_digit = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15", "sixteen": "16", "seventeen": "17", "eighteen": "18",
    "nineteen": "19", "twenty": "20", "thirty-two": "32"
}

# Convert text numbers to digits
def word_to_number(text):
    units = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9
    }
    teens = {
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
        "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19
    }
    tens = {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90
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
# Simplify memory capacity
def simplify_memory_capacity(text):
    if pd.isna(text) or str(text).strip() == "":
        return None

    text = str(text).strip()

    # Try numeric match first
    match = re.search(r"(\d+)", text)
    if match:
        return match.group(1)

    # If not, try converting a word to number
    converted = word_to_number(text)
    return converted if converted else text


# Extract DIMM slot count
def word_slot_extractor(text):
    text = text.lower().strip()

    match = re.search(r"\b(\d+)\s+dimm\s+(slots?|sockets?)", text)
    if match:
        return match.group(1)

    match_word = re.match(r"\b([a-z\-]+)\b.*?(dimm\s+(slots?|sockets?))", text)
    if match_word:
        num = word_to_number(match_word.group(1))
        if num:
            return num

    match = re.search(r"in\s+(\d+)\s+dimm[s]?", text)
    if match:
        return match.group(1)

    match = re.search(r"(\d+)\s*(x)?\s*.*?(dimm\s+(slots?|sockets?))", text, re.IGNORECASE)
    if match:
        return match.group(1)

    for word, digit in word_to_digit.items():
        if re.search(r"\b" + re.escape(word) + r"\b", text):
            text = re.sub(r"\b" + re.escape(word) + r"\b", digit, text)
            break

    match = re.search(r"(\d+)\s*(x)?\s*.*?(dimm\s+(slots?|sockets?))", text, re.IGNORECASE)
    if match:
        return match.group(1)

    return None

# Extract memory capacity and DIMM size
def extract_memory_fields(spec):
    try:
        data = json.loads(spec)
        extracted_capacity = None
        extracted_dimm_size = None
        all_sizes = []

        def extract_from_list(items):
            nonlocal extracted_capacity, all_sizes
            for item in items:
                if not isinstance(item, str):
                    continue
                if not extracted_capacity:
                    extracted_capacity = word_slot_extractor(item)

                matches = re.findall(r"(?:up to\s*)?(\d+(?:\.\d+)?)\s*(TB|GB)", item, re.IGNORECASE)
                for val, unit in matches:
                    val = float(val)
                    gb_val = val * (1024 if unit.upper() == "TB" else 1)
                    all_sizes.append((gb_val, f"{int(val) if val.is_integer() else val}{unit.upper()}"))

        memory = data.get("System Memory", {})

        if isinstance(memory.get("Memory"), dict):
            mem_dict = memory["Memory"]
            slot_val = mem_dict.get("Slot Count")
            if slot_val:
                extracted_capacity = word_slot_extractor(slot_val)

            items = mem_dict.get("Items")
            if isinstance(items, list):
                extract_from_list(items)
            elif isinstance(items, str):
                extract_from_list([items])

        if isinstance(memory.get("Memory"), list):
            extract_from_list(memory["Memory"])

        if isinstance(memory.get("Memory Capacity"), list):
            extract_from_list(memory["Memory Capacity"])
        if isinstance(data.get("Memory Capacity"), list):
            extract_from_list(data["Memory Capacity"])

        if isinstance(memory.get("Memory Type"), list):
            extract_from_list(memory["Memory Type"])
        if isinstance(data.get("Memory Type"), list):
            extract_from_list(data["Memory Type"])

        if isinstance(memory.get("DIMM Sizes"), list):
            extract_from_list(memory["DIMM Sizes"])
        if isinstance(data.get("DIMM Sizes"), list):
            extract_from_list(data["DIMM Sizes"])

        if isinstance(data.get("System Memory (per Node)"), dict):
            node = data.get("System Memory (per Node)")
            if isinstance(node.get("Memory"), list):
                extract_from_list(node["Memory"])

        if all_sizes:
            extracted_dimm_size = max(all_sizes, key=lambda x: x[0])[1]

        return pd.Series({
            "Memory Capacity": extracted_capacity,
            "DIMM Sizes": extracted_dimm_size
        })

    except Exception:
        return pd.Series({"Memory Capacity": None, "DIMM Sizes": None})

# Final version: extract chipset recursively from any nesting
def extract_chipset(spec):
    try:
        data = json.loads(spec)

        def find_chipset(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key.strip().lower() == "chipset":
                        if isinstance(value, list):
                            return value[0]
                        elif isinstance(value, str):
                            return value
                    result = find_chipset(value)
                    if result:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_chipset(item)
                    if result:
                        return result
            return None

        return find_chipset(data)
    except:
        return None

# Match check functions
def check_dimm_slot_match(row):
    try:
        if str(row["server_specification"]).strip() == "{}":
            return "Datas are not available"
        if pd.isna(row["dimm_slots"]) or pd.isna(row["Memory Capacity"]):
            return "missing"
        slot_num = str(int(float(row["dimm_slots"]))).strip()
        memory_capacity = str(row["Memory Capacity"]).strip()
        return "match" if slot_num == memory_capacity else "mismatch"
    except:
        return "error"

def check_memory_size_match(row):
    try:
        if str(row["server_specification"]).strip() == "{}":
            return "Datas are not available"
        if pd.isna(row["maximum_memory"]) or pd.isna(row["DIMM Sizes"]):
            return "missing"

        max_mem = re.search(r"(\d+(?:\.\d+)?)", str(row["maximum_memory"]))
        dimm_size = re.search(r"(\d+(?:\.\d+)?)", str(row["DIMM Sizes"]))

        if max_mem and dimm_size:
            return "match" if float(max_mem.group(1)) == float(dimm_size.group(1)) else "mismatch"
        else:
            return "mismatch"
    except:
        return "error"

def check_chipset_match(row):
    try:
        if pd.isna(row["chipset"]) or pd.isna(row["Verified_chipset"]):
            return "missing"
        return "match" if str(row["chipset"]).strip().lower() == str(row["Verified_chipset"]).strip().lower() else "mismatch"
    except:
        return "error"

# Run memory extraction
memory_df = df["server_specification"].apply(extract_memory_fields)
memory_df["server_description"] = df["server_description"]
memory_df["server_specification"] = df["server_specification"]
memory_df["host_url"] = df["host_url"]
memory_df["dimm_slots"] = df["dimm_slots"]
memory_df["maximum_memory"] = df["maximum_memory"]
memory_df["chipset"] = df["chipset"]

# Build final_df
final_df = memory_df[[
    "server_description",
    "server_specification",
    "host_url",
    "dimm_slots",
    "maximum_memory",
    "chipset",
    "Memory Capacity",
    "DIMM Sizes"
]].copy()

# Apply chipset extraction BEFORE exporting
final_df.loc[:, "Verified_chipset"] = final_df["server_specification"].apply(extract_chipset)

# Apply match checks
final_df.loc[:, "dimm_slot_match"] = final_df.apply(check_dimm_slot_match, axis=1)
final_df.loc[:, "memory_size_match"] = final_df.apply(check_memory_size_match, axis=1)
final_df.loc[:, "chipset_match"] = final_df.apply(check_chipset_match, axis=1)
# Save everything
final_df.to_csv("extracted_memory_info.csv", index=False)
print("Saved to 'extracted_memory_info.csv'")

# Save only problematic rows
problem_rows = final_df[
    final_df["dimm_slot_match"].isin(["mismatch", "missing", "Datas are not available"]) |
    final_df["memory_size_match"].isin(["mismatch", "missing", "Datas are not available"]) |
    final_df["chipset_match"].isin(["mismatch", "missing"])
]
problem_rows.to_csv("problem_memory_rows.csv", index=False)
print("Saved problems to 'problem_memory_rows.csv'")



                      

    

                    
            





    
        


