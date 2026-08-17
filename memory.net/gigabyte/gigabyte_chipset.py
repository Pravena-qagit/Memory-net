import pandas as pd
import json
import re

# Load data
df = pd.read_csv("cleaned_gigabyte_db_import.csv")

# --- Chipset extractor ---
def extract_chipset(spec):
    try:
        if not isinstance(spec, str) or not spec.strip():
            return None

        data = json.loads(spec)

        def clean_chipset(value):
            value = re.sub(r"\u00ae|®", "", value)
            value = re.sub(r"\bexpress\s+chipset\b", "", value, flags=re.IGNORECASE)
            value = re.sub(r"\bchipset\b", "", value, flags=re.IGNORECASE)
            value = re.sub(r"(north|south)\s+bridge\s*:\s*", "", value, flags=re.IGNORECASE)
            value = value.strip()
            value = re.sub(r"\b([A-Z])\s+(\d+)\b", r"\1\2", value)  # 'Z 790' => 'Z790'
            value = re.sub(r"\s{2,}", " ", value)
            return value

        def recursive_search(d):
            if isinstance(d, dict):
                for k, v in d.items():
                    if k.strip().lower() == "chipset":
                        if isinstance(v, list):
                            cleaned = [clean_chipset(x) for x in v if isinstance(x, str)]
                            filtered = [x for x in cleaned if x and x.lower() not in ["®", "\u00ae"]]
                            combined = " ".join(filtered).strip()
                            return [combined] if combined else None
                        elif isinstance(v, str):
                            lines = v.strip().splitlines()
                            cleaned_lines = [clean_chipset(line) for line in lines if line.strip()]
                            return [line for line in cleaned_lines if line.strip()]
                    result = recursive_search(v)                        
                    if result:
                        return result
            elif isinstance(d, list):
                for item in d:
                    result = recursive_search(item)
                    if result:
                        return result
            return None

        result = recursive_search(data)
        return result if result else None

    except Exception as e:
        print(f"Error extracting chipset: {e}")
        return None

# --- Chipset matcher ---
def normalize_chipset_list(chipset_list):
    normalized = []
    for item in chipset_list:
        cleaned = re.sub(r"\s+", "", item)             # remove all spaces
        cleaned = re.sub(r"\u00ae|®", "", cleaned)      # remove symbols
        cleaned = cleaned.lower()
        normalized.append(cleaned)
    return sorted(normalized)

def compare_chipset(row):
    original = row.get("chipset")
    extracted = row.get("Extracted Chipset")

    if not original or not isinstance(extracted, list):
        return "no chipset data is found in the serverspecification row"

    try:
        original_list = eval(original) if isinstance(original, str) else original
        original_norm = normalize_chipset_list(original_list)
        extracted_norm = normalize_chipset_list(extracted)
        return "match" if original_norm == extracted_norm else "mismatch"
    except:
        return "mismatch"

# --- Apply logic to dataset ---
df["Extracted Chipset"] = df["server_specification"].apply(extract_chipset)
df["Chipset Match"] = df.apply(compare_chipset, axis=1)

# --- Save output ---
final_df = df[[
    "server_description", "server_specification", "host_url",
    "chipset", "Extracted Chipset", "Chipset Match"
]]
final_df.to_csv("chipset_extraction_results.csv", index=False)
print("Saved to 'chipset_extraction_results.csv'")

# --- Save mismatches only ---
problem_rows = final_df[final_df["Chipset Match"] != "match"]
problem_rows.to_csv("problem_chipset_rows.csv", index=False)
print("Saved mismatches to 'problem_chipset_rows.csv'")
