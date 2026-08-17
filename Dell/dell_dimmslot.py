import re
import os
import ast
import pandas as pd
from pdfminer.high_level import extract_text

# =========================
# CONFIGURATION
# =========================
CSV_PATH = "/mnt/data/dell.csv"
PDF_DIR = "/mnt/data"

# =========================
# UTILITIES
# =========================

WORD_TO_NUM = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "eight": 8,
    "sixteen": 16
}

def normalize_number(value):
    value = value.lower()
    if value.isdigit():
        return int(value)
    return WORD_TO_NUM.get(value)

# =========================
# PDF EXTRACTION
# =========================

def extract_pdf_text(pdf_path):
    return extract_text(pdf_path).lower()

# =========================
# SECTION EXTRACTION
# =========================

def extract_memory_section(text):
    start_patterns = [
        r'\bmemory specifications\b',
        r'\bmemory\b'
    ]

    end_patterns = [
        r'\bports and connectors\b',
        r'\bexternal ports\b',
        r'\bcommunications\b',
        r'\bstorage\b'
    ]

    start_index = None
    end_index = None

    for pattern in start_patterns:
        match = re.search(pattern, text)
        if match:
            start_index = match.start()
            break

    if start_index is None:
        return ""

    for pattern in end_patterns:
        match = re.search(pattern, text[start_index:])
        if match:
            end_index = start_index + match.start()
            break

    return text[start_index:end_index] if end_index else text[start_index:]

# =========================
# DIMM SLOTS EXTRACTION
# =========================

def extract_dimm_slots(text):
    patterns = [
        r'dimm slots?\s*[:\-]?\s*(\w+)',
        r'dimmslots?\s*[:\-]?\s*(\w+)',
        r'memory slots?\s*[:\-]?\s*(\w+)',
        r'slots?\s*up to\s*(\w+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_number(match.group(1))

    return None

# =========================
# MAX MEMORY EXTRACTION
# =========================
def extract_max_memory(text):
    matches = re.findall(r'(\d+)\s*(gb|tb)', text)
    memory_values = []

    for value, unit in matches:
        value = int(value)
        if unit == 'tb':
            value *= 1024
        memory_values.append(value)

    return max(memory_values) if memory_values else None

# =========================
# MAIN TEST LOGIC
# =========================

def test_pdf_vs_csv():
    df = pd.read_csv(CSV_PATH)

    for index, row in df.iterrows():
        pdf_file = row["file_name"]
        pdf_path = os.path.join(PDF_DIR, pdf_file)

        if not os.path.exists(pdf_path):
            print(f"❌ PDF not found: {pdf_file}")
            continue

        print(f"\n🔍 Validating: {pdf_file}")

        full_text = extract_pdf_text(pdf_path)
        memory_text = extract_memory_section(full_text)

        pdf_dimm = extract_dimm_slots(memory_text)
        pdf_max_mem = extract_max_memory(memory_text)

        csv_dimm = int(ast.literal_eval(row["dimm_slots"])[0])
        csv_max_mem = int(
            ast.literal_eval(row["maximum_memory"])[0]
            .replace("GB", "")
            .strip()
        )

        assert pdf_dimm == csv_dimm, (
            f"DIMM SLOT MISMATCH in {pdf_file}: "
            f"PDF={pdf_dimm}, CSV={csv_dimm}"
        )

        assert pdf_max_mem == csv_max_mem, (
            f"MAX MEMORY MISMATCH in {pdf_file}: "
            f"PDF={pdf_max_mem}GB, CSV={csv_max_mem}GB"
        )

        print("✅ PASSED")

# =========================
# RUN
# =========================

if __name__ == "__main__":
    test_pdf_vs_csv()
