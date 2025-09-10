import requests
import base64
import json

email = "jontyshaw@btinternet.com"
password = "Google321!"
credentials = base64.b64encode(f"{email}:{password}".encode()).decode()

url = "https://hsp-prod.rockshore.net/api/v1/serviceDetails"
headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json"
}

# Load RIDs from file
with open('pad_oxf_rids.txt', 'r') as f:
    rids = [line.strip() for line in f.readlines() if line.strip()]

print(f"Analyzing {len(rids)} PAD → OXF services...")

all_services = []

for rid in rids:
    try:
        response = requests.post(url, json={"rid": rid}, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            service_details = data.get("serviceAttributesDetails", {})
            
            locations = service_details.get("locations", [])
            toc_code = service_details.get("toc_code", "")
            date_of_service = service_details.get("date_of_service", "")
            
            if locations:
                # Extract timing data
                departure_station = locations[0]
                arrival_station = locations[-1]
                
                service_info = {
                    "rid": rid,
                    "toc": toc_code,
                    "date": date_of_service,
                    "departure": {
                        "station": departure_station["location"],
                        "scheduled": departure_station.get("gbtt_ptd", ""),
                        "actual": departure_station.get("actual_td", ""),
                    },
                    "arrival": {
                        "station": arrival_station["location"], 
                        "scheduled": arrival_station.get("gbtt_pta", ""),
                        "actual": arrival_station.get("actual_ta", ""),
                    },
                    "all_locations": locations
                }
                
                all_services.append(service_info)
                
                # Calculate delay
                dep_delay = ""
                arr_delay = ""
                
                if service_info["departure"]["scheduled"] and service_info["departure"]["actual"]:
                    if service_info["departure"]["scheduled"] != service_info["departure"]["actual"]:
                        dep_delay = " (DELAYED)"
                
                if service_info["arrival"]["scheduled"] and service_info["arrival"]["actual"]:
                    if service_info["arrival"]["scheduled"] != service_info["arrival"]["actual"]:
                        arr_delay = " (DELAYED)"
                
                print(f"✓ {rid}: {service_info['departure']['scheduled']} → {service_info['arrival']['actual']}{arr_delay} ({toc_code})")
            
    except Exception as e:
        print(f"✗ {rid}: Error - {e}")

print(f"\n=== SUMMARY ===")
print(f"Successfully analyzed {len(all_services)} services")

# Performance statistics
on_time_departures = sum(1 for s in all_services 
                        if s["departure"]["scheduled"] == s["departure"]["actual"])
on_time_arrivals = sum(1 for s in all_services 
                      if s["arrival"]["scheduled"] == s["arrival"]["actual"])

print(f"On-time departures: {on_time_departures}/{len(all_services)} ({on_time_departures/len(all_services)*100:.1f}%)")
print(f"On-time arrivals: {on_time_arrivals}/{len(all_services)} ({on_time_arrivals/len(all_services)*100:.1f}%)")

# Save detailed data to JSON
with open('pad_oxf_analysis.json', 'w') as f:
    json.dump(all_services, f, indent=2)

print(f"\nDetailed data saved to pad_oxf_analysis.json")