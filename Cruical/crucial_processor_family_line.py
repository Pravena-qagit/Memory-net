import ast
import csv
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path


MAIN_CSV = Path(
    os.getenv(
        "MAIN_CSV",
        os.getenv(
            "ASROCK_CSV",
            r"C:\Users\bitco\Documents\cisco_pytest\Cruical\ASRock_crucial_db_import.csv",
        ),
    )
)
INTEL_CSV = Path(
    os.getenv(
        "INTEL_CSV",
        r"C:\Users\bitco\Documents\cisco_pytest\Cruical\12022026_intel_db_import.csv",
    )
)
AMD_CSV = Path(
    os.getenv(
        "AMD_CSV",
        r"C:\Users\bitco\Documents\cisco_pytest\Cruical\09022026_amd_db_import.csv",
    )
)

# By default, validate every row from the selected brand's main CSV.
VALIDATION_LIMIT = int(os.getenv("VALIDATION_LIMIT", "0"))


def derive_main_csv_label(csv_path):
    brand = re.sub(r"_crucial_db_import$", "", csv_path.stem, flags=re.IGNORECASE)
    brand = brand.replace("_", " ").strip()
    return f"{brand} Crucial" if brand else "Main CSV"


MAIN_CSV_LABEL = os.getenv("MAIN_CSV_LABEL", derive_main_csv_label(MAIN_CSV))
VALIDATION_OUTPUT_CSV = Path(
    os.getenv(
        "VALIDATION_OUTPUT_CSV",
        str(
            Path(__file__).with_name(
                f"{MAIN_CSV_LABEL.lower().replace(' ', '_')}_processor_validation_pytest_output.csv"
            )
        ),
    )
)


def parse_list(value):
    """Parse list-like CSV cells such as "['Intel...', 'AMD...']"."""
    if value is None:
        return []

    value = value.strip()
    if not value:
        return []

    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return [value]

    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]

    parsed_value = str(parsed).strip()
    return [parsed_value] if parsed_value else []


def parse_list_for_duplicate_check(value):
    """Extract list items even when a CSV list cell has a small quote issue."""
    if value is None:
        return []

    value = value.strip()
    if not value:
        return []

    parsed = parse_list(value)
    if not (value.startswith("[") and "," in value):
        return parsed

    inner = value[1:-1] if value.endswith("]") else value[1:]
    fallback = [
        item.strip().strip("'\"").strip()
        for item in inner.split(",")
    ]
    fallback = [item for item in fallback if item]

    return fallback or parsed


def normalize(value):
    """Normalize CPU names/family/line text for comparison."""
    value = unicodedata.normalize("NFKC", value or "")
    value = value.replace("®", "").replace("™", "")
    value = value.replace("Â®", "").replace("â„¢", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip().casefold()


def load_product_index():
    """Build lookup from Intel/AMD product_name to product family and line."""
    product_index = {}

    for csv_path, source in ((INTEL_CSV, "Intel"), (AMD_CSV, "AMD")):
        with csv_path.open(newline="", encoding="utf-8-sig") as file:
            for row in csv.DictReader(file):
                product_name = (row.get("product_name") or "").strip()
                if not product_name:
                    continue

                product_index.setdefault(normalize(product_name), []).append(
                    {
                        "source": source,
                        "product_name": product_name,
                        "product_family": (row.get("product_family") or "").strip(),
                        # AMD file has processor_series instead of product_line.
                        "product_line": (
                            row.get("product_line") or row.get("processor_series") or ""
                        ).strip(),
                    }
                )

    return product_index


def duplicate_entries(values):
    counts = Counter()
    first_seen = {}

    for value in values:
        key = normalize(value)
        if not key:
            continue
        counts[key] += 1
        first_seen.setdefault(key, value)

    return [
        (first_seen[key], count)
        for key, count in counts.items()
        if count > 1
    ]


def duplicate_summary(entries):
    return " | ".join(
        f"{value} appears {count} times"
        for value, count in entries
    )


def match_family_line(matched, normalized_families, normalized_lines):
    family_matches = bool(matched["product_family"]) and (
        normalize(matched["product_family"]) in normalized_families
    )
    line_matches = (
        not matched["product_line"]
        or normalize(matched["product_line"]) in normalized_lines
    )
    return family_matches, line_matches


def best_reference_match(matches, normalized_families, normalized_lines):
    for matched in matches:
        family_matches, line_matches = match_family_line(
            matched,
            normalized_families,
            normalized_lines,
        )
        if family_matches and line_matches:
            return matched, family_matches, line_matches

    matched = matches[0]
    family_matches, line_matches = match_family_line(
        matched,
        normalized_families,
        normalized_lines,
    )
    return matched, family_matches, line_matches


def reference_duplicate_detail(processor, matches):
    references = []
    for matched in matches:
        references.append(
            f"{matched['source']} CSV product_name [{matched['product_name']}], "
            f"family [{matched['product_family']}], line [{matched['product_line']}]"
        )
    return (
        f"{processor} -> found {len(matches)} matching product_name rows in "
        f"Intel/AMD CSVs: {'; '.join(references)}"
    )


def mismatch_info(processor, matched, main_families, main_lines):
    expected_families = {normalize(family) for family in main_families}
    expected_lines = {normalize(line) for line in main_lines}
    mismatch_values = []
    family_mismatch = False
    line_mismatch = False

    if matched["product_family"] and normalize(matched["product_family"]) not in expected_families:
        family_mismatch = True
        mismatch_values.append(f"family: {matched['product_family']}")

    if matched["product_line"] and normalize(matched["product_line"]) not in expected_lines:
        line_mismatch = True
        mismatch_values.append(matched["product_line"])

    if len(mismatch_values) == 1:
        detail = f"['{processor}' -> '{mismatch_values[0]}']"
    else:
        detail = f"['{processor}' -> '{'; '.join(mismatch_values)}']"

    return {
        "detail": detail,
        "family_mismatch": family_mismatch,
        "line_mismatch": line_mismatch,
    }


def build_reason(
    match_count,
    missing_count,
    family_match_count,
    family_mismatch_count,
    line_match_count,
    line_mismatch_count,
    no_family_count,
    duplicate_processor_count,
    duplicate_processor_family_count,
    duplicate_processor_line_count,
):
    reason_parts = []
    if missing_count:
        reason_parts.append(f"{missing_count} missing from Intel/AMD product_name")
    if family_match_count:
        reason_parts.append(f"{family_match_count} processor family matched")
    if family_mismatch_count:
        reason_parts.append(f"{family_mismatch_count} processor family mismatches")
    if line_match_count:
        reason_parts.append(f"{line_match_count} processor line matched")
    if line_mismatch_count:
        reason_parts.append(f"{line_mismatch_count} processor line mismatches")
    if no_family_count:
        reason_parts.append(
            f"{no_family_count} have no {MAIN_CSV_LABEL} processor_family mapping"
        )
    if duplicate_processor_count:
        reason_parts.append(
            f"{duplicate_processor_count} duplicate processor values in "
            f"{MAIN_CSV_LABEL} processor column"
        )
    if duplicate_processor_family_count:
        if duplicate_processor_family_count == 1:
            reason_parts.append("one duplicate in processor family")
        else:
            reason_parts.append(
                f"{duplicate_processor_family_count} duplicates in processor family"
            )
    if duplicate_processor_line_count:
        if duplicate_processor_line_count == 1:
            reason_parts.append("one duplicate in processor line")
        else:
            reason_parts.append(
                f"{duplicate_processor_line_count} duplicates in processor line"
            )
    return "; ".join(reason_parts) + "."


def row_status(
    match_count,
    family_match_count,
    line_match_count,
    missing_count,
    mismatch_count,
    no_family_count,
    duplicate_processor_count,
    duplicate_processor_family_count,
    duplicate_processor_line_count,
    total_processors,
):
    if total_processors == 0:
        return "No processors in main CSV"

    statuses = []
    if match_count or family_match_count or line_match_count:
        statuses.append("match")
    if missing_count:
        statuses.append("missing")
    if mismatch_count:
        statuses.append("mismatch")
    if no_family_count:
        statuses.append("No family is mapped in main CSV")
    if (
        duplicate_processor_count
        or duplicate_processor_family_count
        or duplicate_processor_line_count
    ):
        statuses.append("duplicate")

    return " | ".join(statuses)


def validate_main_csv_rows(limit=VALIDATION_LIMIT):
    product_index = load_product_index()
    validation_rows = []

    with MAIN_CSV.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for main_csv_row_number, row in enumerate(reader, start=2):
            if limit and len(validation_rows) >= limit:
                break

            processors = parse_list(row.get("processor"))
            main_families = parse_list_for_duplicate_check(row.get("processor_family"))
            main_lines = parse_list_for_duplicate_check(row.get("processor_line"))
            normalized_families = {normalize(family) for family in main_families}
            normalized_lines = {normalize(line) for line in main_lines}
            duplicate_processors = duplicate_entries(processors)
            duplicate_processor_count = sum(
                count - 1
                for _, count in duplicate_processors
            )
            duplicate_processor_families = duplicate_entries(main_families)
            duplicate_processor_family_count = sum(
                count - 1
                for _, count in duplicate_processor_families
            )
            duplicate_processor_lines = duplicate_entries(main_lines)
            duplicate_processor_line_count = sum(
                count - 1
                for _, count in duplicate_processor_lines
            )

            matched_processors = []
            missing_processors = []
            mismatch_processors = []
            no_family_processors = []
            family_match_count = 0
            family_mismatch_count = 0
            line_match_count = 0
            line_mismatch_count = 0

            for processor in processors:
                matches = product_index.get(normalize(processor), [])

                if not matches:
                    missing_processors.append(processor)
                    continue

                if not main_families:
                    no_family_processors.append(processor)
                    continue

                matched, family_matches, line_matches = best_reference_match(
                    matches,
                    normalized_families,
                    normalized_lines,
                )

                if family_matches:
                    family_match_count += 1
                else:
                    family_mismatch_count += 1

                if line_matches:
                    line_match_count += 1
                else:
                    line_mismatch_count += 1

                if family_matches and line_matches:
                    matched_processors.append(processor)
                else:
                    mismatch = mismatch_info(processor, matched, main_families, main_lines)
                    mismatch_processors.append(mismatch["detail"])

            total_processors = len(processors)
            match_count = len(matched_processors)
            missing_count = len(missing_processors)
            mismatch_count = len(mismatch_processors)
            no_family_count = len(no_family_processors)

            if total_processors == 0:
                reason = (
                    f"No processor values are present in "
                    f"{MAIN_CSV_LABEL} processor column."
                )
            else:
                reason = build_reason(
                    match_count,
                    missing_count,
                    family_match_count,
                    family_mismatch_count,
                    line_match_count,
                    line_mismatch_count,
                    no_family_count,
                    duplicate_processor_count,
                    duplicate_processor_family_count,
                    duplicate_processor_line_count,
                )

            validation_rows.append(
                {
                    "main_csv_row": main_csv_row_number,
                    "server_description": row.get("server_description", ""),
                    "option_part_no": row.get("option_part_no", ""),
                    "processor": " | ".join(processors),
                    "total_processors": total_processors,
                    "match_count": match_count,
                    "missing_count": missing_count,
                    "mismatch_count": mismatch_count,
                    "no_family_mapped_count": no_family_count,
                    "duplicate_processor_count": duplicate_processor_count,
                    "duplicate_processor_family_count": duplicate_processor_family_count,
                    "duplicate_processor_line_count": duplicate_processor_line_count,
                    "status": row_status(
                        match_count,
                        family_match_count,
                        line_match_count,
                        missing_count,
                        mismatch_count,
                        no_family_count,
                        duplicate_processor_count,
                        duplicate_processor_family_count,
                        duplicate_processor_line_count,
                        total_processors,
                    ),
                    "main_processor_family": " | ".join(main_families),
                    "main_processor_line": " | ".join(main_lines),
                    "reason": reason,
                    "duplicate_processor_data": duplicate_summary(duplicate_processors),
                    "duplicate_processor_family_data": duplicate_summary(
                        duplicate_processor_families
                    ),
                    "duplicate_processor_line_data": duplicate_summary(
                        duplicate_processor_lines
                    ),
                    "missing_data": " | ".join(missing_processors),
                    "mismatch_data": " | ".join(mismatch_processors),
                }
            )

    return validation_rows


def write_validation_csv(validation_rows):
    VALIDATION_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    with VALIDATION_OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=list(validation_rows[0].keys()))
        writer.writeheader()
        writer.writerows(validation_rows)


def test_main_csv_processor_family_line_mapping():
    validation_rows = validate_main_csv_rows()
    write_validation_csv(validation_rows)

    problem_rows = [
        row
        for row in validation_rows
        if row["missing_count"] != 0
        or row["mismatch_count"] != 0
        or row["no_family_mapped_count"] != 0
        or row["duplicate_processor_count"] != 0
        or row["duplicate_processor_family_count"] != 0
        or row["duplicate_processor_line_count"] != 0
        or row["total_processors"] == 0
    ]

    assert not problem_rows, (
        f"Processor validation failed for {len(problem_rows)} "
        f"{MAIN_CSV_LABEL} row(s). "
        f"See details in: {VALIDATION_OUTPUT_CSV}"
    )
