import pandas as pd
import re 
# cleaning functions def clean_processor_name(name): name = re.sub(r"[^\w\s-]", "", str(name)) name = name.strip() name = " ".join(name.split()) return name.lower() # Convert Gigabyte processor column into a list def get_clean_processor_list(x): try: proc_list = eval(x) if not isinstance(proc_list, list): proc_list = [str(proc_list)] except: proc_list = [str(x)] return [clean_processor_name(p) for p in proc_list if p] print("Loading files") gigabyte_df = pd.read_csv("30082025_reordered_file.csv", low_memory=False) intel_df = pd.read_csv("intel_raw_csv_latest.csv", low_memory=False) # clean intel product names intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name) # Create lookup dictionaries intel_name_to_family = dict( zip(intel_df["clean_product_name"], intel_df["product_family"]) ) intel_clean_set = set(intel_df["clean_product_name"]) # clean gigabyte processors gigabyte_df["clean_processor"] = gigabyte_df["processor"].apply( get_clean_processor_list ) # exact match logic for processor names def exact_match_processor_list(lst): matched_names = [] matched_families = [] for p in lst: if p in intel_clean_set: matched_names.append(p) family = intel_name_to_family.get(p) if family: matched_families.append(family) return list(set(matched_names)), list(set(matched_families)) gigabyte_df["mapped_product_name"], gigabyte_df["mapped_product_family"] = zip( *gigabyte_df["clean_processor"].apply(exact_match_processor_list) ) gigabyte_df["status"] = gigabyte_df["mapped_product_name"].apply( lambda x: "match" if len(x) > 0 else "mismatch" ) gigabyte_df.to_csv("final_intel_matched_output.csv", index=False) print("Saved final_intel_matched_output.csv")
# cleaning functions
def clean_processor_name(name):
    name = re.sub(r"[^\w\s-]", "", str(name))
    name = name.strip()
    name = " ".join(name.split())
    return name.lower()

# Convert Gigabyte processor column into a list
def get_clean_processor_list(x):
    try:
        proc_list = eval(x)
        if not isinstance(proc_list, list):
            proc_list = [str(proc_list)]
    except:
        proc_list = [str(x)]
    return [clean_processor_name(p) for p in proc_list if p]

print("Loading files")
gigabyte_df = pd.read_csv("30082025_reordered_file.csv", low_memory=False)
intel_df = pd.read_csv("19052025_intel_processors.csv", low_memory=False)

# clean intel product names
intel_df["clean_product_name"] = intel_df["product_name"].apply(clean_processor_name)

# Create lookup dictionaries
intel_name_to_family = dict(
    zip(intel_df["clean_product_name"], intel_df["product_family"])
)
intel_clean_set = set(intel_df["clean_product_name"])

# clean gigabyte processors
gigabyte_df["clean_processor"] = gigabyte_df["processor"].apply(
    get_clean_processor_list
)

# exact match logic for processor names
def exact_match_processor_list(lst):
    matched_names = []
    matched_families = []
    for p in lst:
        if p in intel_clean_set:
            matched_names.append(p)
            family = intel_name_to_family.get(p)
            if family:
                matched_families.append(family)
    return list(set(matched_names)), list(set(matched_families))

gigabyte_df["mapped_product_name"], gigabyte_df["mapped_product_family"] = zip(
    *gigabyte_df["clean_processor"].apply(exact_match_processor_list)
)

gigabyte_df["status"] = gigabyte_df["mapped_product_name"].apply(
    lambda x: "match" if len(x) > 0 else "mismatch"
)

gigabyte_df.to_csv("old_intel_matched_output.csv", index=False)
print("Saved old_intel_matched_output.csv")