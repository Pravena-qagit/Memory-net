import pandas as pd

# Helper function to read the CSV file
def read_csv(file_path):
    return pd.read_csv(file_path)

# Helper function to form the SKU based on the provided columns
def generate_expected_sku(row):
    # Capacity (numeric part)
    capacity = str(row['capacity']).replace('GB', '')
    capacity = int(capacity)
    
    # Memory Type (First letter + last number)
    memory_type = row['memory_type'][0] + row['memory_type'][-1] if 'DDR' in row['memory_type'] else 'D4'
    
    # ECC (E for ECC, N for Non-ECC)
    ecc = 'N' if 'Non-ECC' in row['ecc'] else 'E' if 'ECC' in row['ecc'] else None
    
    # DIMM Type (first letter)
    dimm_type = row['dimm_type'][0]  # First letter
    
    # Ranks and Rank Width
    ranks = int(row['ranks'])
    rank_width = int(row['rank_width'])
    
    # Speed (remove any periods)
    speed = int(row['speed'])
    
    # Voltage (remove 'V', remove any periods)
    voltage = str(row['voltage']).replace('V', '').replace('.', '')
    
    # Height (first letter)
    height = row['height'][0]  # First letter of height
    
    # Quantity
    qty = int(row['qty'])
    
    # Form SKU
    return f"{capacity}{memory_type}{ecc}{dimm_type}{ranks}{rank_width}{speed}{voltage}{height}{qty}"

# Function to process the CSV and write to a new CSV with the memory_SKU column
def process_and_save_csv(input_file, output_file):
    # Read the CSV into a pandas DataFrame
    df = read_csv(input_file)

    # List to hold the new SKU values
    skus = []
    status = []  # List to hold the status of each comparison (Match, Unmatch, Missing)

    # Generate memory_SKU for each row
    for index, row in df.iterrows():
        actual_sku = row['product_id']  # Assuming the actual SKU is in a column named 'product_id'
        
        # Check if actual_sku is NaN, if so, mark as Missing and skip the comparison
        if pd.isna(actual_sku):
            skus.append(None)  # Append None or skip as per requirement
            status.append("Missing")  # Mark as Missing
        else:
            # Generate the expected SKU and append it
            expected_sku = generate_expected_sku(row)
            skus.append(expected_sku)
            
            # Compare generated SKU with actual SKU
            if expected_sku == actual_sku:
                status.append("Match")  # Mark as Match if both are the same
            else:
                status.append("Unmatch")  # Mark as Unmatch if they differ
    
    # Add the generated memory_SKU and status columns to the DataFrame
    df['generated_memory_SKU'] = skus
    df['status'] = status

    # Write the DataFrame with the new memory_SKU and status columns to a new CSV file
    df.to_csv(output_file, index=False)
    print(f"Processed data saved to {output_file}")

# Example usage:
input_file = "final_output1.csv"  # Replace with your input CSV path
output_file = "processed_memory_sku_with_status.csv"  # The new output file path

# Process the file and save the new CSV
process_and_save_csv(input_file, output_file)