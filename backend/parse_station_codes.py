import csv
import json

def parse_station_codes():
    """Parse the station codes CSV and create comprehensive mappings."""
    stations = {}  # name -> code mapping

    with open('station_codes (07-12-2020).csv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f)

        for row in reader:
            # Each row has 4 pairs: name1, code1, name2, code2, name3, code3, name4, code4
            for i in range(0, len(row), 2):
                if i + 1 < len(row) and row[i].strip() and row[i+1].strip():
                    station_name = row[i].strip()
                    station_code = row[i+1].strip()
                    stations[station_code] = station_name

    # Sort by station name for easier searching
    sorted_stations = dict(sorted(stations.items(), key=lambda x: x[1]))

    # Write to JSON file
    with open('all_station_codes.json', 'w', encoding='utf-8') as f:
        json.dump(sorted_stations, f, indent=2, ensure_ascii=False)

    print(f"Parsed {len(sorted_stations)} stations")
    print(f"Sample entries:")
    for i, (code, name) in enumerate(list(sorted_stations.items())[:5]):
        print(f"  {code}: {name}")

if __name__ == "__main__":
    parse_station_codes()
