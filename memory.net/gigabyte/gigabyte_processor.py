import pandas as pd
import json
import re
import ast

# Load data
df = pd.read_csv("29072025_gigabyte_db_import (2).csv")


def normalize(text):
    text = re.sub(r'\s+', ' ', text.lower().strip())
    return text


def expand_gen_word(line):
    line = re.sub(r'(\b\d{1,2}(st|nd|rd|th)?)\s*gen\b', r'\1 Generation', line, flags=re.I)
    line = re.sub(r'(\b\d{1,2}(st|nd|rd|th)?)gen\b', r'\1 Generation', line, flags=re.I)  
    line = re.sub(r'\bgen\b', 'Generation', line, flags=re.I)
    return line



def expand_slash_versions(line):
    """
    Expand slash-separated processor versions into multiple processor strings.
    Handles both '2nd/1st Gen' and generic 'V6/V5' patterns.
    """
    proc_match = re.search(r'\bprocessors?\b', line, re.I)
    proc_suffix = proc_match.group(0).lower() if proc_match else 'processor'

    # Unified slash regex: detect version1/version2 ("V6/V5")
    version_slash_match = re.search(r'([A-Za-z0-9\-\.]+)\/([A-Za-z0-9\-\.]+)', line)
    if version_slash_match:
        first_ver = version_slash_match.group(1)
        second_ver = version_slash_match.group(2)

        # Check if it is a "Gen" version (e.g. "2nd/1st Gen")
        gen_match = re.search(r'{}\s*Gen'.format(re.escape(version_slash_match.group(0))), line, re.I)
        if gen_match:
            # Format like: "{} Gen Intel Xeon processors"
            template = line.replace(version_slash_match.group(0), "{}")
            template = re.sub(r'processors?', proc_suffix, template, flags=re.I)
            return [
                expand_gen_word(template.format(first_ver).strip()),
                expand_gen_word(template.format(second_ver).strip())
            ]
        else:
            # Generic version pattern: e.g. "Intel Xeon V6/V5 processor"
            prefix = line[:version_slash_match.start()]
            suffix = line[version_slash_match.end():]

            prefix_clean = re.sub(r'\bprocessors?\b', '', prefix, flags=re.I).strip()
            suffix_clean = re.sub(r'\bprocessors?\b', '', suffix, flags=re.I).strip()

            core = f"{prefix_clean} {suffix_clean}".strip()

            return [
                expand_gen_word(f"{core} {first_ver} {proc_suffix}".strip()),
                expand_gen_word(f"{core} {second_ver} {proc_suffix}".strip())
            ]

    # No slash to expand
    return [expand_gen_word(line)]


def extract_and_clean_processor(spec_data):
    if not isinstance(spec_data, str) or not spec_data.strip():
        return None
    try:
        spec = json.loads(spec_data)
    except Exception:
        return None

    keys = ["CPU", "APU", "Superchip"]
    all_lines = []
    for key in keys:
        if key in spec:
            raw = spec[key]
            if isinstance(raw, str):
                all_lines.append(raw)
            elif isinstance(raw, list):
                all_lines.extend(raw)
            elif isinstance(raw, dict):
                all_lines.extend(list(raw.values()))

    if not all_lines:
        return None

    combined_lines = []
    if all(isinstance(x, str) and len(x) <= 50 for x in all_lines):
        temp = []
        for token in all_lines:
            token = re.sub(r'[®™©]', '', token).strip()
            if not token or re.search(r'(TDP|nm|10nm|watt|power|socket|cache|threads?|cores?)', token, re.I):
                continue
            # Preferred keywords, plus keep ASIC/Bridge for special cases
            if re.search(r'(intel|amd|epyc|xeon|core|ryzen|celeron|pentium|processor|cpu|asic|bridge|nvmeof)', token, re.I):
                temp.append(token)
        phrase = ""
        final_phrases = []
        for word in temp:
            if len(word.split()) <= 3 and not word.lower().endswith("processor"):
                phrase += word + " "
            else:
                phrase += word
                final_phrases.append(phrase.strip())
                phrase = ""
        if phrase:
            final_phrases.append(phrase.strip())
        combined_lines.extend(final_phrases)
    else:
        for line in all_lines:
            if isinstance(line, str):
                combined_lines.append(line)

    processed = []
    for line in combined_lines:
        line = re.sub(r'[®™©]', '', line).strip()
        line = re.sub(r'\.', '', line)  

        
        line = re.sub(r'\bDual\b', '', line, flags=re.I).strip()
        line = re.sub(r'\bproduct\b', '', line, flags=re.I).strip()
        line = line.lstrip('-•').strip()
        line = re.sub(r'\bfamily\b', '', line, flags=re.I).strip()

        # First: TRY TO CAPTURE EMBEDDED PROCESSOR DESCRIPTION EARLY
        embedded_match = re.search(
            r'(Intel|AMD|Celeron|Pentium|Xeon|Core)[^()\n]*CPU', line, re.I)
        if embedded_match:
            extracted = embedded_match.group(0).strip()
            processed.append(expand_gen_word(extracted))
            continue

        # Accept as processor if it's a known special hardware processor/ASIC/Bridge
        if re.search(r'\b(asic|bridge|nvmeof|nvme\s*over\s*fabrics)\b', line, re.I):
            # Add 'processor' if not present
            if not re.search(r'processor[s]?\b', line, re.I):
                line += ' processor'
            processed.append(expand_gen_word(line))
            continue

        # Skip technical lines
        if re.search(r'(TDP|Watt|Power|NOTE|nm|cores?|threads?|socket|cache|PCIe|lithography)', line, re.I):
            continue

        expanded_lines = expand_slash_versions(line)
        for exp_line in expanded_lines:
            exp_line = re.sub(r'\.', '', exp_line) 
            if re.search(r'(Intel|AMD|EPYC|Xeon|Ryzen|Core|Pentium|Celeron|Processor|CPU|ASIC|Bridge)', exp_line, re.I):
                # Same embedded processor extraction after slash expansion
                embedded_exp_match = re.search(
                    r'(Intel|AMD|Celeron|Pentium|Xeon|Core)[^()\n]*CPU', exp_line, re.I)
                if embedded_exp_match:
                    extracted = embedded_exp_match.group(0).strip()
                    processed.append(expand_gen_word(extracted))
                    continue

                if re.search(r'built[-\s]?in.*(Intel|AMD).+CPU', exp_line, re.I):
                    match = re.search(r'((Intel|AMD)[^()\n]*CPU)', exp_line, re.I)
                    if match:
                        processed.append(expand_gen_word(match.group(1).strip()))
                    continue

                if re.match(r'^\d+\s*x\s+.+APU', exp_line, re.I) and any(re.search(r'(core|compute unit)', l, re.I) for l in all_lines):
                    desc = [exp_line]
                    for l in all_lines:
                        l = re.sub(r'[®™©]', '', str(l)).strip()
                        if re.search(r'(core|compute unit)', l, re.I):
                            desc.append(re.sub(r'^[-•]\s*', '', l))
                    return [expand_gen_word(" - ".join(desc))]

                # Add processor suffix if missing
                if not re.search(r'processor[s]?\b', exp_line, re.I) and not exp_line.lower().endswith("cpu"):
                    exp_line += ' processor'
                processed.append(expand_gen_word(re.sub(r'\s+', ' ', exp_line.strip())))

    seen = set()
    final = []
    for item in processed:
        norm = normalize(item)
        if norm not in seen:
            final.append(item)
            seen.add(norm)

    return final if final else None


def compare_processor(row):
    original = row.get("processor")
    extracted = row.get("Extracted_Processor")
    spec_data = row.get("server_specification")

    try:
        spec = json.loads(spec_data) if isinstance(spec_data, str) else {}
    except Exception:
        return "invalid_json"

    if not any(key in spec for key in ["CPU", "APU", "Superchip"]):
        return "data is not in the server_specification"

    if not original or not extracted:
        return "no_data"

    try:
        original_list = ast.literal_eval(original) if isinstance(original, str) else original
        extracted_list = ast.literal_eval(extracted) if isinstance(extracted, str) else extracted
    except Exception:
        return "invalid_data"

    def clean_item(item):
        item = re.sub(r'[\'\"\[\]]', '', str(item))
        item = re.sub(r'\bfamily\b', '', item, flags=re.I)
        item = re.sub(r'\bprocessors?\b', '', item, flags=re.I) 
        item = expand_gen_word(item)
        return normalize(item)

    def collapse_extracted(items):
        collapsed = []
        current = []
        for item in items:
            parts = item.split()
            current.extend(parts)
            if "cpu" in item.lower() or "processor" in item.lower() or len(current) >= 3:
                collapsed.append(" ".join(current))
                current = []
        if current:
            collapsed.append(" ".join(current))
        return collapsed

    original_set = set(clean_item(x) for x in original_list if isinstance(x, str))
    extracted_collapsed = collapse_extracted(extracted_list)
    extracted_set = set(clean_item(x) for x in extracted_collapsed)

    return "match" if original_set == extracted_set else "mismatch"


# Apply functions
df["Extracted_Processor"] = df["server_specification"].apply(extract_and_clean_processor)
df["Processor_Match"] = df.apply(compare_processor, axis=1)

# Save output CSV files
columns = ["server_description", "server_specification", "host_url", "processor", "Extracted_Processor", "Processor_Match"]
df[columns].to_csv("updated_processor_extraction_results.csv", index=False)
df[df["Processor_Match"] != "match"][columns].to_csv("updated_problem_processor_rows.csv", index=False)

print("Saved: updated_processor_extraction_results.csv")
print("Mismatches saved: updated_problem_processor_rows.csv")

print("\n=== SUMMARY ===")
print(df["Processor_Match"].value_counts())

print("\n=== EXAMPLES ===")
for match_type in df["Processor_Match"].unique():
    print(f"\n{match_type.upper()} Examples:")
    sample = df[df["Processor_Match"] == match_type].head(2)
    for _, row in sample.iterrows():
        print(f" ➤ Server: {row['server_description']}")
        print(f" Original: {row['processor']}")
        print(f" Extracted: {row['Extracted_Processor']}")
        print(" ---")
