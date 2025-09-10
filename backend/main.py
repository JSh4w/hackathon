from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import uvicorn
import httpx
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import os
import openai
import json 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    RAIL_EMAIL: str
    RAIL_PWORD: str
    OPENAI_API_KEY: str
    
    class Config:
        env_file = ".env"

settings = Settings()

DETAILS = "https://hsp-prod.rockshore.net/api/v1/serviceDetails"
METRICS = "https://hsp-prod.rockshore.net/api/v1/serviceMetrics"

app = FastAPI(title="Hackathon API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ServiceMetricsRequest(BaseModel):
    from_loc: str
    to_loc: str
    from_time: str
    to_time: str
    from_date: str
    to_date: str
    days: str
    toc_filter: Optional[List[str]] = None
    tolerance: Optional[List[str]] = None

class HSPCredentials(BaseModel):
    email: str
    password: str

async def get_service_metrics(request: ServiceMetricsRequest, credentials: HSPCredentials):
    auth_string = base64.b64encode(f"{credentials.email}:{credentials.password}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from_loc": request.from_loc,
        "to_loc": request.to_loc,
        "from_time": request.from_time,
        "to_time": request.to_time,
        "from_date": request.from_date,
        "to_date": request.to_date,
        "days": request.days
    }
    
    if request.toc_filter:
        payload["toc_filter"] = request.toc_filter
    if request.tolerance:
        payload["tolerance"] = request.tolerance
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(METRICS, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTPError: {e}")
            if 'response' in locals():
                logger.error(f"Status: {response.status_code}, Response: {response.text}")
                raise HTTPException(status_code=500, detail=f"HSP API error: Status {response.status_code} - {response.text}")
            else:
                raise HTTPException(status_code=500, detail=f"HSP API error: {str(e)}")
        except Exception as e:
            logger.error(f"Exception: {e}")
            raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "API is running"}

@app.get("/")
async def root():
    return {"message": "Welcome to Hackathon API", "version": "1.0.0"}

@app.get("/api/v1/details")
async def get_details():
    return {"details_url": DETAILS, "message": "Service details endpoint"}

@app.get("/api/v1/metrics")
async def get_metrics():
    return {"metrics_url": METRICS, "message": "Service metrics endpoint"}

@app.get("/service")
async def request_service_metrics():
    credentials = HSPCredentials(email=settings.RAIL_EMAIL, password=settings.RAIL_PWORD)
    request = ServiceMetricsRequest(
        from_loc="EUS",
        to_loc="KGL",
        from_time="0700",
        to_time="1900",
        from_date="2024-01-01",
        to_date="2024-01-31",
        days="WEEKDAY"
    )
    try:
        print(request, credentials)
        result = await get_service_metrics(request, credentials)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.get("/api/v1/service-metrics/simple")
async def request_simple_service_metrics():
    credentials = HSPCredentials(email=settings.RAIL_EMAIL, password=settings.RAIL_PWORD)
    request = ServiceMetricsRequest(
        from_loc="EUS",
        to_loc="KGL",
        from_time="0700",
        to_time="1900",
        from_date="2024-01-01",
        to_date="2024-01-31",
        days="WEEKDAY"
    )
    
    try:
        result = await get_service_metrics(request, credentials)
        logger.info(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

def calculate_delay_minutes(scheduled_time: str, actual_time: str) -> Optional[int]:
    """Calculate delay in minutes between scheduled and actual time"""
    if not scheduled_time or not actual_time or scheduled_time == actual_time:
        return 0
    
    try:
        # Convert HHMM format to minutes
        sch_hours = int(scheduled_time[:2])
        sch_minutes = int(scheduled_time[2:])
        act_hours = int(actual_time[:2])
        act_minutes = int(actual_time[2:])
        
        scheduled_total = sch_hours * 60 + sch_minutes
        actual_total = act_hours * 60 + act_minutes
        
        # Handle day rollover (if actual time is next day)
        if actual_total < scheduled_total:
            actual_total += 24 * 60
            
        return actual_total - scheduled_total
    except (ValueError, IndexError):
        return None

async def get_service_details_by_rid(rid: str, credentials: HSPCredentials) -> Optional[Dict[str, Any]]:
    """Get service details for a specific RID"""
    auth_string = base64.b64encode(f"{credentials.email}:{credentials.password}".encode()).decode()
    
    headers = {
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(DETAILS, headers=headers, json={"rid": rid}, timeout=30)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"RID {rid}: HTTP {response.status_code} - {response.text[:100]}")
            return None
        except Exception as e:
            logger.warning(f"RID {rid}: Exception - {str(e)}")
            return None

@app.get("/api/v1/delays/histogram")
async def get_delay_histogram():
    """Get histogram data for departure and arrival delays from Paddington->Havant route"""
    try:
        # Read RIDs from file
        rid_file_path = os.path.join(os.path.dirname(__file__), "pad_oxf_rids.txt")
        
        if not os.path.exists(rid_file_path):
            raise HTTPException(status_code=404, detail="RID file not found")
        
        with open(rid_file_path, 'r') as f:
            rids = [line.strip() for line in f.readlines() if line.strip()]
        
        credentials = HSPCredentials(email=settings.RAIL_EMAIL, password=settings.RAIL_PWORD)
        
        departure_delays = []
        arrival_delays = []
        all_departure_delays = []  # Include all delays for on-time calculation
        all_arrival_delays = []    # Include all delays for on-time calculation
        extreme_departure_delays = 0
        extreme_arrival_delays = 0
        
        for rid in rids:
            service_data = await get_service_details_by_rid(rid, credentials)
            
            if service_data and "serviceAttributesDetails" in service_data:
                locations = service_data.get("serviceAttributesDetails", {}).get("locations", [])
                
                if locations:
                    # First station (departure)
                    first_station = locations[0]
                    dep_delay = calculate_delay_minutes(
                        first_station.get("gbtt_ptd", ""),
                        first_station.get("actual_td", "")
                    )
                    if dep_delay is not None:
                        all_departure_delays.append(dep_delay)  # Always include for on-time calc
                        if dep_delay > 30:
                            extreme_departure_delays += 1
                        else:
                            departure_delays.append(dep_delay)  # Only for average calc
                    
                    # Last station (arrival) 
                    last_station = locations[-1]
                    arr_delay = calculate_delay_minutes(
                        last_station.get("gbtt_pta", ""),
                        last_station.get("actual_ta", "")
                    )
                    if arr_delay is not None:
                        all_arrival_delays.append(arr_delay)  # Always include for on-time calc
                        if arr_delay > 30:
                            extreme_arrival_delays += 1
                        else:
                            arrival_delays.append(arr_delay)  # Only for average calc
        
        # Create histogram bins (0 to +30 minutes) - no negative since nothing arrives/departs early
        bins = list(range(0, 31, 3))  # 3-minute bins for better visibility: 0-3, 3-6, 6-9, etc.
        
        def create_histogram(delays: List[int], bins: List[int]) -> Dict[str, int]:
            histogram = {}
            for i in range(len(bins) - 1):
                bin_label = f"{bins[i]} to {bins[i+1]}"
                count = sum(1 for delay in delays if bins[i] <= delay < bins[i+1])
                histogram[bin_label] = count
            
            # Handle outliers
            early_outliers = sum(1 for delay in delays if delay < 0)
            late_outliers = sum(1 for delay in delays if delay >= bins[-1])
            
            # Add early arrivals/departures to the "0-3 min" bucket (they're on time or early)
            if "0 to 3" in histogram:
                histogram["0 to 3"] += early_outliers
            elif early_outliers > 0:
                histogram["0 to 3"] = early_outliers
                
            if late_outliers > 0:
                histogram[f"{bins[-1]}+ min"] = late_outliers
                
            return histogram
        
        return {
            "route": "Paddington → Havant",
            "total_services": len(rids),
            "analyzed_services": len(all_departure_delays),
            "departure_delays": {
                "histogram": create_histogram(departure_delays, bins),
                "avg_delay": sum(departure_delays) / len(departure_delays) if departure_delays else 0,
                "on_time_count": sum(1 for d in all_departure_delays if d <= 0),  # Use ALL delays for on-time
                "extreme_delays": extreme_departure_delays
            },
            "arrival_delays": {
                "histogram": create_histogram(arrival_delays, bins),
                "avg_delay": sum(arrival_delays) / len(arrival_delays) if arrival_delays else 0,
                "on_time_count": sum(1 for d in all_arrival_delays if d <= 0),  # Use ALL delays for on-time
                "extreme_delays": extreme_arrival_delays
            }
        }
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="RID file not found")
    except Exception as e:
        logger.error(f"Error generating histogram: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating histogram: {str(e)}")

@app.post("/api/v1/ai-analysis")
async def get_ai_analysis():
    """Get AI analysis of delay patterns and predictions"""
    try:
        # First get the histogram data
        histogram_data = await get_delay_histogram()
        
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Prepare data for AI analysis
        analysis_prompt = f"""
        You are a railway performance analyst. Analyze the following delay data for the Paddington to Havant railway route and provide insights:

        Route: {histogram_data['route']}
        Total Services Analyzed: {histogram_data['analyzed_services']}
        
        Departure Delays:
        - Average Delay: {histogram_data['departure_delays']['avg_delay']:.1f} minutes
        - On-time Departures: {histogram_data['departure_delays']['on_time_count']}/{histogram_data['analyzed_services']}
        - Delay Distribution: {json.dumps(histogram_data['departure_delays']['histogram'])}
        
        Arrival Delays:
        - Average Delay: {histogram_data['arrival_delays']['avg_delay']:.1f} minutes  
        - On-time Arrivals: {histogram_data['arrival_delays']['on_time_count']}/{histogram_data['analyzed_services']}
        - Delay Distribution: {json.dumps(histogram_data['arrival_delays']['histogram'])}

        Please provide:
        1. Overall performance assessment (good/average/poor)
        2. Key delay patterns you observe
        3. Probability of delays for future journeys (as a percentage)
        4. Expected delay range for a typical journey
        5. Recommendations for travelers
        6. Best time recommendations if patterns suggest it

        Keep your response concise but informative, suitable for a passenger planning their journey.
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert railway analyst providing travel advice based on historical performance data."},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )

        ai_analysis = response.choices[0].message.content
        
        return {
            "histogram_data": histogram_data,
            "ai_analysis": ai_analysis,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating AI analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating AI analysis: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
