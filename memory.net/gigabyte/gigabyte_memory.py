import pandas as pd
import json
import re

df = pd.read_csv("23072025_gigabyte_db_import.csv")

def word_to_number(text):
    if not isinstance(text, str):
        return None
    units = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9
    }
    teens = {
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19
    }
    tens = {
        "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
        "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90
    }
    text = text.lower().replace("-", " ")
    parts = text.split()
    if len(parts) == 1:
        return str(units.get(parts[0], teens.get(parts[0], tens.get(parts[0], ""))))
    if len(parts) == 2 and parts[0] in tens and parts[1] in units:
        return str(tens[parts[0]] + units[parts[1]])
    return None
# Main extractor
def extract_memory_fields(row):
    try:
        spec            = row["server_specification"]
        original_slots  = str(row.get("dimm_slots")).strip()
        original_sizes  = str(row.get("maximum_memory")).strip()

        if not isinstance(spec, str) or not spec.strip():
            raise ValueError("Empty or invalid spec")

        data           = json.loads(spec)
        memory_content = (
            data.get("MemoryInfo", {}).get("Memory", "")
            or data.get("Memory", "")
        )

        if isinstance(memory_content, str):
            memory_lines = memory_content.strip().splitlines()
        elif isinstance(memory_content, list):
            memory_lines = memory_content
        else:
            memory_lines = []

        extracted_slots = None
        extracted_size  = None
        size_candidates = []
        dimm_numbers    = []

        for line in memory_lines:
            if not isinstance(line, str):
                continue

            # Clean‑ups
            line = re.sub(r"\([^)]*\)", "", line)  # drop (…) notes
            line = re.sub(
                r"and\s+\d+(?:\.\d+)?\s*(GB|TB)/s\s+memory\s+bandwidth.*",
                "",
                line,
                flags=re.IGNORECASE,
            )
            line_lower = line.lower()
            if "bandwidth" in line_lower:
                continue

            # Capture GB/TB values
            for val, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(GB|TB)", line, re.IGNORECASE):
                val = float(val)
                size_gb = int(val * 1024) if unit.upper() == "TB" else int(val)
                size_candidates.append((size_gb, f"{size_gb}GB"))

            # Capture DIMM slot count 
            slot_match = re.search(
                r"(\d+)\s*x\s+[^\n]*?dimms?\b(?:\s+(?:slots?|sockets?))?",
                line,
                re.IGNORECASE,
            )
            if slot_match:
                dimm_numbers.append(int(slot_match.group(1)))

            # Up‑to capacity lines
            capacity_match = re.search(
                r"(system\s+memory\s+capacity\s+)?up to\s+(\d+(?:\.\d+)?)\s*(GB|TB)",
                line,
                re.IGNORECASE,
            )
            if capacity_match:
                val  = float(capacity_match.group(2))
                unit = capacity_match.group(3).upper()
                size_gb = int(val * 1024) if unit == "TB" else int(val)
                size_candidates.append((size_gb, f"{size_gb}GB"))

            # “2 x DIMM sockets supporting up to …”
            special_match = re.search(
                r"(\d+)\s*x\s+\w+\s+dimm\s+sockets?.*?up to\s+(\d+(?:\.\d+)?)\s*(GB|TB)",
                line,
                re.IGNORECASE,
            )
            if special_match:
                slots, val, unit = special_match.groups()
                dimm_numbers.append(int(slots))
                val  = float(val)
                unit = unit.upper()
                size_gb = int(val * 1024) if unit == "TB" else int(val)
                size_candidates.append((size_gb, f"{size_gb}GB"))
                continue

            # “per DIMM / per socket …”
            if "per dimm" in line_lower or "per socket" in line_lower:
                for val, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(GB|TB)", line, re.IGNORECASE):
                    val = float(val)
                    size_gb = int(val * 1024) if unit.upper() == "TB" else int(val)
                    size_candidates.append((size_gb, f"{size_gb}GB"))
                continue

            # Plain word‑ or digit‑based slot counts
            dimm_match = re.findall(
                r"\b(\d+)\s*(x)?\s*(\w+\s+)?(so-)?dimm\s+(slots?|sockets?)",
                line_lower,
            )
            if dimm_match:
                dimm_numbers.extend(int(m[0]) for m in dimm_match)
            else:
                for word_num in re.findall(
                    r"\b([a-z\-]+)\s*(x)?\s*(\w+\s+)?dimm\s+(slots?|sockets?)",
                    line_lower,
                ):
                    num = word_to_number(word_num[0])
                    if num:
                        dimm_numbers.append(int(num))

        # ── Pick highest capacity & slot count ──
        if size_candidates:
            extracted_size = max(size_candidates, key=lambda x: x[0])[1]
        if dimm_numbers:
            extracted_slots = str(max(dimm_numbers))

        return pd.Series({
            "Extracted DIMM Slots A": "[]" if original_slots == "[]" else f"['{extracted_slots}']" if extracted_slots else None,
            "Extracted DIMM Sizes":   "[]" if original_sizes == "[]" else f"['{extracted_size}']"  if extracted_size  else None,
        })

    except Exception as e:
        print(f"Error parsing row: {e}")
        return pd.Series({
            "Extracted DIMM Slots A": None,
            "Extracted DIMM Sizes":   None,
        })

# Comparison helpers
def compare_dimm_slots(row):
    spec = row["server_specification"]
    if not isinstance(spec, str) or spec.strip() == "{}":
        return "datas is not available"

    original  = str(row["dimm_slots"]).strip()
    extracted = row["Final Extracted DIMM Slots"]

    if original == "[]" and extracted == "[]":
        return "dimm slots is not available in server specification"
    if not original or not extracted:
        return "missing"

    original_num  = re.search(r"\d+", original)
    extracted_num = re.search(r"\d+", extracted)
    if original_num and extracted_num:
        return "match" if original_num.group() == extracted_num.group() else "mismatch"
    return "missing"

def compare_memory_size(row):
    spec = row["server_specification"]
    if not isinstance(spec, str) or spec.strip() == "{}":
        return "datas is not available"

    original  = str(row["maximum_memory"]).strip()
    extracted = row["Extracted DIMM Sizes"]

    if original == "[]" and extracted == "[]":
        return "max memory is not available in server specification"
    if not original or not extracted:
        return "missing"

    original_val  = re.search(r"\d+", original)
    extracted_val = re.search(r"\d+", extracted)
    if original_val and extracted_val:
        return "match" if original_val.group() == extracted_val.group() else "mismatch"
    return "missing"

# Fallback extractor
def extract_dimm_and_max_memory(spec):
    try:
        if not isinstance(spec, str) or not spec.strip():
            raise ValueError("Invalid or empty server_specification")

        data        = json.loads(spec)
        memory_data = (
            data.get("MemoryInfo", {}).get("Memory", "")
            or data.get("Memory", "")
        )
        if isinstance(memory_data, str):
            memory_data = memory_data.strip().splitlines()
        elif isinstance(memory_data, list):
            memory_data = [str(x).strip() for x in memory_data]
        else:
            memory_data = []

        extracted_slots       = None
        extracted_max_memory  = None

        for line in memory_data:
            if not isinstance(line, str):
                continue

            if not extracted_slots:
                m = re.search(
                    r"(\d+)\s*x\s+[^\n]*?dimms?\b(?:\s+(?:slots?|sockets?))?",
                    line,
                    re.IGNORECASE,
                )
                if m:
                    extracted_slots = m.group(1)

            if not extracted_max_memory and "total" in line.lower():
                mem = re.search(r"(\d+(?:\.\d+)?)\s*(GB|TB)", line, re.IGNORECASE)
                if mem:
                    val, unit = mem.groups()
                    unit = unit.upper()
                    extracted_max_memory = f"{int(float(val)*1024) if unit=='TB' else int(float(val))}GB"

        return pd.Series({
            "Extracted DIMM Slots B":     extracted_slots,
            "Extracted Maximum Memory B": extracted_max_memory,
        })

    except Exception as e:
        print(f"Error in fallback extractor: {e}")
        return pd.Series({
            "Extracted DIMM Slots B":     None,
            "Extracted Maximum Memory B": None,
        })

# Run both extractors & merge 
memory_df   = df.apply(extract_memory_fields, axis=1)
fallback_df = df["server_specification"].apply(extract_dimm_and_max_memory)
full_df     = pd.concat([df, memory_df, fallback_df], axis=1)

# Prefer main extractor; fall back if needed
full_df["Final Extracted DIMM Slots"] = full_df["Extracted DIMM Slots A"].combine_first(
    full_df["Extracted DIMM Slots B"].apply(
        lambda x: f"['{x}']" if pd.notna(x) else None
    )
)

# Compare against originals 
full_df["DIMM Slot Match"]  = full_df.apply(compare_dimm_slots, axis=1)
full_df["Memory Size Match"] = full_df.apply(compare_memory_size, axis=1)

# Save results
final_df = full_df[
    [
        "server_description",
        "server_specification",
        "host_url",
        "dimm_slots",
        "maximum_memory",
        "Final Extracted DIMM Slots",
        "Extracted DIMM Sizes",
        "DIMM Slot Match",
        "Memory Size Match",
    ]
]
final_df.to_csv("extracted_gigabyte_memory_info2.csv", index=False)
print("Output saved to 'extracted_gigabyte_memory_info2.csv'")

# Log only problematic rows
problem_rows = final_df[
    final_df["DIMM Slot Match"].isin(["mismatch", "missing", "datas is not available", "dimm slots is not available in server specification", "max memory is not available in server specification"]) |
    final_df["Memory Size Match"].isin(["mismatch", "missing", "datas is not available", "dimm slots is not available in server specification", "max memory is not available in server specification"])
]
problem_rows.to_csv("problem_memory_rows2.csv", index=False)
print("Saved problems to 'problem_memory_rows2.csv'")
