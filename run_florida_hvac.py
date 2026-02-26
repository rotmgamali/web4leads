import subprocess
import time

cities = [
    "Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", 
    "Hialeah", "Port St. Lucie", "Tallahassee", "Cape Coral", "Fort Lauderdale",
    "Pembroke Pines", "Hollywood", "Miramar", "Gainesville", "Coral Springs",
    "Clearwater", "Palm Bay", "Pompano Beach", "Lakeland", "West Palm Beach",
    "Miami Gardens", "Davie", "Boca Raton", "Sunrise", "Plantation",
    "Deltona", "Palm Coast", "Largo", "Melbourne", "Deerfield Beach",
    "Boynton Beach", "Fort Myers", "Homestead", "Kissimmee", "North Port",
    "Daytona Beach", "Tamarac", "Weston", "Wellington", "Ocala",
    "Port Orange", "Jupiter", "Sanford", "Margate", "Coconut Creek",
    "Sarasota", "Pensacola", "Bradenton", "Pinellas Park", "Bonita Springs"
]

sheet_name = "Web4Guru Leads"
base_query = "HVAC companies in {}, FL"

def run_scraper():
    # Chunk queries to avoid one massive process run, though scraper handles list.
    # Passing all at once allows the scraper to manage the browser session efficienty.
    
    queries = [base_query.format(city) for city in cities]
    
    cmd = [
        "python3", "google_maps_scraper.py",
        "--sheet-name", sheet_name,
        "--queries"
    ] + queries
    
    print(f"Starting scraper for {len(queries)} cities in Florida...")
    subprocess.run(cmd)

if __name__ == "__main__":
    run_scraper()
