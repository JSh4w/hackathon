import requests
import base64

email = "jontyshaw@btinternet.com"
password = "Google321!"
credentials = base64.b64encode(f"{email}:{password}".encode()).decode()

url = "https://hsp-prod.rockshore.net/api/v1/serviceDetails"
headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json"
}

# Target route - change these as needed
TARGET_FROM = "PAD"  # Paddington
TARGET_TO = "HWV"   # Havant

matching_rids = []

print(f"Searching for all {TARGET_FROM} → {TARGET_TO} journeys...")

# Search multiple date patterns and RID ranges
# Your original working pattern was 201607294210xxx (2016-07-29 4:21)
# Let's try variations around that successful pattern

# Base pattern that worked: 20160729421
base_pattern = "20160729421"

# Try different sequence ranges around your working RIDs (0016-0169)
# Your working RIDs were: 201607294210077 to 201607294210169
# Let's search broader ranges around this area

# Based on the pattern analysis, I can see:
# - 4:20 has mostly PAD departures (to CDF, SWA, CNM, BRI) 
# - Your original working 4:21 pattern had PAD → HWV in 0077-0169 range
# - Let's focus on the 4:21 pattern with extended ranges

date_patterns = [
    "20160729421",  # Original working hour - focus here
    "20160729422",  # Try next hour
    "20160729423",  # And next 
    "20160729424",  # And next
    # Try earlier morning hours when commuter trains run
    "20160729060",  # 6:00 AM
    "20160729061",  # 6:01 AM
    "20160729070",  # 7:00 AM  
    "20160729071",  # 7:01 AM
    "20160729080",  # 8:00 AM
    "20160729081",  # 8:01 AM
    # Try evening return journeys
    "20160729170",  # 5:00 PM
    "20160729171",  # 5:01 PM
    "20160729180",  # 6:00 PM
    "20160729181",  # 6:01 PM
]

print(f"Searching around the original working date pattern (2016-07-29)")

for date_pattern in date_patterns:
    print(f"\nTrying pattern: {date_pattern}xxxx")
    
    # Focus on ranges based on your working RIDs and the pattern analysis
    # Your working PAD → HWV range was 0077-0169 in the 4:21 hour
    # From 4:20 data, I see valid services clustered in certain ranges
    search_ranges = [
        range(0, 100),       # Check early range first
        range(100, 200),     # Your working range was around here
        range(200, 300),     # Next cluster
        range(300, 400),     # Continue search
        range(400, 500),     # Extended search
        range(500, 600),     # Even more extended
    ]
    
    for search_range in search_ranges:
        print(f"  Searching sequence {search_range.start:04d}-{search_range.stop-1:04d}")
        found_in_range = 0
        
        for i in search_range:
            test_rid = f"{date_pattern}{i:04d}"
            
            try:
                response = requests.post(url, json={"rid": test_rid}, headers=headers, timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    locations = data.get("serviceAttributesDetails", {}).get("locations", [])
                    
                    if locations:
                        first_station = locations[0]["location"]
                        last_station = locations[-1]["location"]
                        found_in_range += 1
                        
                        print(f"✓ {test_rid}: {first_station} → {last_station}")
                        
                        # Check if this matches our target route
                        if first_station == TARGET_FROM and last_station == TARGET_TO:
                            toc_code = data.get("serviceAttributesDetails", {}).get("toc_code", "")
                            matching_rids.append({
                                "rid": test_rid,
                                "toc": toc_code,
                                "data": data
                            })
                            print(f"🎯 MATCH: {test_rid} ({toc_code})")
                            
                            # Stop early if we find enough matches
                            if len(matching_rids) >= 50:
                                print(f"\n✅ Found {len(matching_rids)} matches - stopping search")
                                break
                    else:
                        print(f"✓ {test_rid}: No locations data")
                else:
                    print(f"✗ {test_rid}: HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"✗ {test_rid}: {str(e)}")
        
        print(f"  Found {found_in_range} valid services in range {search_range.start:04d}-{search_range.stop-1:04d}")
        
        # Break inner loop if we have enough matches
        if len(matching_rids) >= 50:
            break
    
    # Break outer loop if we have enough matches
    if len(matching_rids) >= 50:
        break

print(f"\n=== RESULTS ===")
print(f"Found {len(matching_rids)} journeys for {TARGET_FROM} → {TARGET_TO}")

for service in matching_rids:
    print(f"\nRID: {service['rid']} ({service['toc']})")
    locations = service['data']['serviceAttributesDetails']['locations']
    
    # Show key stations with timing
    for loc in locations:
        station = loc['location']
        scheduled_dep = loc.get('gbtt_ptd', '')
        actual_dep = loc.get('actual_td', '')
        scheduled_arr = loc.get('gbtt_pta', '')
        actual_arr = loc.get('actual_ta', '')
        
        if scheduled_dep or scheduled_arr:
            sch_time = scheduled_arr or scheduled_dep
            act_time = actual_arr or actual_dep
            delay = ""
            
            if sch_time and act_time and sch_time != act_time:
                delay = " (DELAYED)"
                
            print(f"  {station}: {sch_time} → {act_time}{delay}")

print(f"\nAll RIDs for {TARGET_FROM} → {TARGET_TO}:")
print([s['rid'] for s in matching_rids])