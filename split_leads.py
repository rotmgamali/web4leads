import csv
import os

input_file = '/Users/mac/Desktop/web4leads/scraped_leads.csv'
output_dir = '/Users/mac/Desktop/web4leads/'
chunk_size = 1000
num_batches = 3

try:
    print(f"Reading from {input_file}...")
    with open(input_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print("Error: File is empty.")
            exit(1)
            
        data = list(reader)
    
    total_rows = len(data)
    print(f"Total data rows found: {total_rows}")
    
    for i in range(num_batches):
        start = i * chunk_size
        end = start + chunk_size
        batch_data = data[start:end]
        
        if not batch_data:
            print(f"Batch {i+1} would be empty (no more data). Stopping.")
            break
            
        output_filename = os.path.join(output_dir, f'leads_batch_{i+1}.csv')
        print(f"Writing {len(batch_data)} rows to {output_filename}...")
        
        with open(output_filename, 'w', encoding='utf-8', newline='') as f_out:
            writer = csv.writer(f_out)
            writer.writerow(header)
            writer.writerows(batch_data)
        print(f"Successfully created {output_filename}")

    if total_rows < (chunk_size * num_batches):
        print(f"\nNote: The input file had {total_rows} rows, which is less than the requested {chunk_size * num_batches} rows (3 batches of 1000).")
        print(f"Only {total_rows // chunk_size + (1 if total_rows % chunk_size else 0)} batches were created.")

except FileNotFoundError:
    print(f"Error: File not found at {input_file}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
