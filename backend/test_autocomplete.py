"""Test autocomplete functionality"""
import json

# Load station codes
with open('all_station_codes.json', 'r', encoding='utf-8') as f:
    ALL_STATION_CODES = json.load(f)

def autocomplete_stations(query, limit=10):
    """Simulate the autocomplete endpoint logic"""
    if not query or len(query) < 1:
        return []

    query_upper = query.upper()
    matches = []

    is_code_query = len(query) == 3 and query.isalpha()

    for code, name in ALL_STATION_CODES.items():
        if code.startswith(query_upper):
            matches.append({
                "code": code,
                "name": name,
                "match_type": "code",
                "display": f"{name} ({code})"
            })
        elif name.upper().startswith(query_upper):
            matches.append({
                "code": code,
                "name": name,
                "match_type": "name",
                "display": f"{name} ({code})"
            })
        elif not is_code_query and query_upper in name.upper():
            matches.append({
                "code": code,
                "name": name,
                "match_type": "partial",
                "display": f"{name} ({code})"
            })

    def sort_key(match):
        if match["match_type"] == "code":
            return (0, match["code"] == query_upper, match["name"])
        elif match["match_type"] == "name":
            return (1, match["name"])
        else:
            return (2, match["name"])

    matches.sort(key=sort_key, reverse=True)
    return matches[:limit]

# Test cases
print("=== Test 1: Search by station name 'London' ===")
results = autocomplete_stations("London", 5)
for r in results:
    print(f"  {r['display']}")

print("\n=== Test 2: Search by 3-letter code 'EUS' ===")
results = autocomplete_stations("EUS", 5)
for r in results:
    print(f"  {r['display']}")

print("\n=== Test 3: Search by partial name 'Brighton' ===")
results = autocomplete_stations("Bright", 5)
for r in results:
    print(f"  {r['display']}")

print("\n=== Test 4: Search by code prefix 'BR' ===")
results = autocomplete_stations("BR", 5)
for r in results:
    print(f"  {r['display']}")

print("\n=== Test 5: Search by partial match 'Airport' ===")
results = autocomplete_stations("Airport", 5)
for r in results:
    print(f"  {r['display']}")

print("\n=== Test 6: Allow 3-letter code to pass through ===")
query = "BTN"
print(f"Query '{query}' is a valid 3-letter code: {len(query) == 3 and query.isalpha()}")
results = autocomplete_stations(query, 5)
for r in results:
    print(f"  {r['display']}")
