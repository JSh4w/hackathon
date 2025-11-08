from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
import time
import asyncio
from cache_manager import cache_manager, IS_PRODUCTION

# Load station code mappings
def load_station_codes() -> Dict[str, str]:
    """Load station code to name mapping"""
    try:
        with open("station_codes.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load station codes: {e}")
        return {}

STATION_CODES = load_station_codes()

def get_station_name(code: str) -> str:
    """Get full station name from code, fallback to code if not found"""
    return STATION_CODES.get(code, code)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Console output
    ]
)
logger = logging.getLogger(__name__)

# Set more verbose logging for httpx to see API requests
logging.getLogger("httpx").setLevel(logging.INFO)

class Settings(BaseSettings):
    RAIL_EMAIL: str
    RAIL_PWORD: str
    OPENAI_API_KEY: str
    CORS_ORIGINS: str = "http://localhost:3000, https://trelay.netlify.app"

    class Config:
        env_file = ".env"

settings = Settings()

# Parse CORS origins from comma-separated string
ALLOWED_ORIGINS = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

DETAILS = "https://hsp-prod.rockshore.net/api/v1/serviceDetails"
METRICS = "https://hsp-prod.rockshore.net/api/v1/serviceMetrics"

app = FastAPI(title="Hackathon API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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

async def get_service_metrics(request: ServiceMetricsRequest, credentials: HSPCredentials, cache_request: bool = True):
    start_time = time.time()

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

    # Try read-through cache first
    cached_service_name = f"metrics_{request.from_loc}_{request.to_loc}_{request.from_date}_{request.to_date}"
    cached = cache_manager.get_cached_service_by_name(cached_service_name)
    if cached and isinstance(cached.get("response"), dict):
        logger.info(f"✅ Cache hit for %s; returning cached metrics", cached_service_name)
        return cached["response"]
    else:
        logger.info(f"❌ Cache miss for %s; fetching from API", cached_service_name)

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            response = await client.post(METRICS, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()

            # Cache the request and response if enabled
            if cache_request:
                duration_ms = int((time.time() - start_time) * 1000)
                rid = cache_manager.generate_rid()

                # Cache metrics
                services_count = len(response_data.get("Services", [])) if isinstance(response_data, dict) else 0
                metrics_data = {
                    "duration_ms": duration_ms,
                    "endpoint": "serviceMetrics",
                    "status_code": response.status_code,
                    "request_size": len(json.dumps(payload)),
                    "response_size": len(json.dumps(response_data)),
                    "route": f"{request.from_loc}->{request.to_loc}",
                    "services_count": services_count
                }
                cache_manager.cache_metrics(rid, metrics_data)

                # Cache detailed service request
                service_name = f"metrics_{request.from_loc}_{request.to_loc}_{request.from_date}_{request.to_date}"
                cache_manager.cache_service_request(service_name, payload, response_data, rid)

                logger.info(f"Cached service metrics request with RID: {rid}")

            return response_data
        except httpx.HTTPError as e:
            logger.error(f"HTTPError: {e}")
            if 'response' in locals():
                logger.error(f"Status: {response.status_code}, Response: {response.text}")
                # Cache error metrics
                if cache_request:
                    duration_ms = int((time.time() - start_time) * 1000)
                    rid = cache_manager.generate_rid()
                    metrics_data = {
                        "duration_ms": duration_ms,
                        "endpoint": "serviceMetrics",
                        "status_code": response.status_code,
                        "request_size": len(json.dumps(payload)),
                        "response_size": len(response.text),
                        "route": f"{request.from_loc}->{request.to_loc}",
                        "error": f"HTTP {response.status_code}: {response.text[:100]}"
                    }
                    cache_manager.cache_metrics(rid, metrics_data)
                raise HTTPException(status_code=500, detail=f"HSP API error: Status {response.status_code} - {response.text}")
            else:
                raise HTTPException(status_code=500, detail=f"HSP API error: {str(e)}")
        except Exception as e:
            logger.error(f"Exception: {e}")
            # Cache error metrics
            if cache_request:
                duration_ms = int((time.time() - start_time) * 1000)
                rid = cache_manager.generate_rid()
                metrics_data = {
                    "duration_ms": duration_ms,
                    "endpoint": "serviceMetrics",
                    "status_code": 0,
                    "route": f"{request.from_loc}->{request.to_loc}",
                    "error": str(e)
                }
                cache_manager.cache_metrics(rid, metrics_data)
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
        from_loc="BTN",
        to_loc="VIC",
        from_time="0700",
        to_time="0800",
        from_date="2016-07-01",
        to_date="2016-07-02",
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
    """
    Calculate delay in minutes between scheduled and actual time
    Returns:
    - Positive number: Late (delay)
    - Negative number: Early
    - 0: On time
    - None: Cancelled or missing data
    """
    # Check for missing scheduled time (shouldn't happen but be safe)
    if not scheduled_time:
        return None

    # Check for cancelled service (no actual time recorded)
    if not actual_time:
        return None  # This indicates cancellation

    if scheduled_time == actual_time:
        return 0

    try:
        # Convert HHMM format to minutes since midnight
        sch_hours = int(scheduled_time[:2])
        sch_minutes = int(scheduled_time[2:])
        act_hours = int(actual_time[:2])
        act_minutes = int(actual_time[2:])

        scheduled_total = sch_hours * 60 + sch_minutes
        actual_total = act_hours * 60 + act_minutes

        # Handle day rollover - but be more careful about this
        # Only add 24 hours if the difference is more than 12 hours (likely next day)
        time_diff = actual_total - scheduled_total
        if time_diff < -720:  # More than 12 hours early suggests next day
            actual_total += 24 * 60
        elif time_diff > 720:  # More than 12 hours late suggests previous day
            actual_total -= 24 * 60

        return actual_total - scheduled_total
    except (ValueError, IndexError):
        return None

def get_station_delays(locations: List[Dict[str, Any]], origin_station: str, destination_station: str) -> tuple[Optional[int], Optional[int], Optional[str], Optional[str]]:
    """Get departure and arrival delays for specific origin and destination stations, plus cancellation reasons"""
    departure_delay = None
    arrival_delay = None
    departure_cancel_reason = None
    arrival_cancel_reason = None

    for location in locations:
        station_code = location.get("location", "")

        # Check for departure from origin station
        if station_code == origin_station:
            scheduled_dep = location.get("gbtt_ptd", "")
            actual_dep = location.get("actual_td", "")
            cancel_reason = location.get("late_canc_reason", "")

            if scheduled_dep:
                if actual_dep:
                    departure_delay = calculate_delay_minutes(scheduled_dep, actual_dep)
                elif cancel_reason:
                    # Has cancellation reason but no actual time = cancelled
                    departure_cancel_reason = cancel_reason
                else:
                    # No actual time and no reason = cancelled (reason unknown)
                    departure_cancel_reason = "Service cancelled"

        # Check for arrival at destination station
        if station_code == destination_station:
            scheduled_arr = location.get("gbtt_pta", "")
            actual_arr = location.get("actual_ta", "")
            cancel_reason = location.get("late_canc_reason", "")

            if scheduled_arr:
                if actual_arr:
                    arrival_delay = calculate_delay_minutes(scheduled_arr, actual_arr)
                elif cancel_reason:
                    # Has cancellation reason but no actual time = cancelled
                    arrival_cancel_reason = cancel_reason
                else:
                    # No actual time and no reason = cancelled (reason unknown)
                    arrival_cancel_reason = "Service cancelled"

    return departure_delay, arrival_delay, departure_cancel_reason, arrival_cancel_reason

async def get_service_details_by_rid(rid: str, credentials: HSPCredentials, cache_request: bool = True) -> Optional[Dict[str, Any]]:
    """Get service details for a specific RID"""
    start_time = time.time()

    auth_string = base64.b64encode(f"{credentials.email}:{credentials.password}".encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_string}",
        "Content-Type": "application/json"
    }

    # Read-through cache first by service name
    cached_service_name = f"details_{rid}"
    cached = cache_manager.get_cached_service_by_name(cached_service_name)
    if cached and isinstance(cached.get("response"), dict):
        logger.info(f"✅ Cache hit for %s; returning cached details", cached_service_name)
        return cached["response"]
    else:
        logger.info(f"❌ Cache miss for %s; fetching from API", cached_service_name)

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            payload = {"rid": rid}
            response = await client.post(DETAILS, headers=headers, json=payload)
            if response.status_code == 200:
                response_data = response.json()

                # Cache the request and response if enabled
                if cache_request:
                    duration_ms = int((time.time() - start_time) * 1000)
                    cache_rid = cache_manager.generate_rid()

                    # Cache metrics
                    metrics_data = {
                        "duration_ms": duration_ms,
                        "endpoint": "serviceDetails",
                        "status_code": response.status_code,
                        "request_size": len(json.dumps(payload)),
                        "response_size": len(json.dumps(response_data)),
                        "route": f"details_{rid}",
                        "services_count": 1
                    }
                    cache_manager.cache_metrics(cache_rid, metrics_data)

                    # Cache detailed service request
                    service_name = f"details_{rid}"
                    cache_manager.cache_service_request(service_name, payload, response_data, cache_rid)

                    logger.debug(f"Cached service details request for RID {rid} with cache RID: {cache_rid}")

                return response_data
            else:
                logger.warning(f"RID {rid}: HTTP {response.status_code} - {response.text[:100]}")
                # Cache error if enabled
                if cache_request:
                    duration_ms = int((time.time() - start_time) * 1000)
                    cache_rid = cache_manager.generate_rid()
                    metrics_data = {
                        "duration_ms": duration_ms,
                        "endpoint": "serviceDetails",
                        "status_code": response.status_code,
                        "route": f"details_{rid}",
                        "error": f"HTTP {response.status_code}: {response.text[:100]}"
                    }
                    cache_manager.cache_metrics(cache_rid, metrics_data)
            return None
        except Exception as e:
            logger.warning(f"RID {rid}: Exception - {str(e)}")
            # Cache error if enabled
            if cache_request:
                duration_ms = int((time.time() - start_time) * 1000)
                cache_rid = cache_manager.generate_rid()
                metrics_data = {
                    "duration_ms": duration_ms,
                    "endpoint": "serviceDetails",
                    "status_code": 0,
                    "route": f"details_{rid}",
                    "error": str(e)
                }
                cache_manager.cache_metrics(cache_rid, metrics_data)
            return None

@app.post("/api/v1/journey-analysis")
async def analyze_journey(request: ServiceMetricsRequest):
    """Get histogram data for departure and arrival delays from any route for the last month"""
    logger.info("="*60)
    logger.info(f"🚄 JOURNEY ANALYSIS STARTED")
    logger.info(f"📍 Route: {request.from_loc} → {request.to_loc}")
    logger.info(f"🕐 Time: {request.from_time} - {request.to_time}")
    logger.info(f"📅 Date Range: {request.from_date} to {request.to_date}")
    logger.info(f"📋 Days: {request.days}")
    logger.info("="*60)

    try:
        credentials = HSPCredentials(email=settings.RAIL_EMAIL, password=settings.RAIL_PWORD)

        logger.info("🔐 Credentials loaded, requesting service metrics...")
        # Get service metrics data for the specified route and date range
        metrics_data = await get_service_metrics(request, credentials)

        if not metrics_data or "Services" not in metrics_data:
            logger.error("❌ No service data found in API response")
            raise HTTPException(status_code=404, detail="No service data found for the specified route and date range")

        services = metrics_data["Services"]
        logger.info(f"✅ Found {len(services)} service patterns to analyze")

        # Extract RIDs from services - RIDs are in serviceAttributesMetrics.rids as arrays
        logger.info("🔍 Extracting RIDs from service patterns...")
        rids = []
        for i, service in enumerate(services, 1):
            if isinstance(service, dict) and "serviceAttributesMetrics" in service:
                service_rids = service["serviceAttributesMetrics"].get("rids", [])
                departure_time = service["serviceAttributesMetrics"].get("gbtt_ptd", "unknown")
                arrival_time = service["serviceAttributesMetrics"].get("gbtt_pta", "unknown")
                if service_rids:
                    rids.extend(service_rids)  # Add all RIDs from this service
                    logger.info(f"  📋 Service {i}: {departure_time}→{arrival_time} - {len(service_rids)} RIDs")

        logger.info(f"🎯 Extracted {len(rids)} total RIDs for detailed analysis")
        logger.info("-"*60)

        departure_delays = []
        arrival_delays = []
        cancelled_departures = 0
        cancelled_arrivals = 0
        cancellation_reasons = {
            "departure": [],
            "arrival": []
        }
        processed_count = 0

        # Process each RID individually to get detailed service data
        logger.info(f"🔄 Processing {len(rids)} individual journeys...")
        progress_interval = max(1, len(rids) // 20)  # Show progress every 5%

        for idx, rid in enumerate(rids, 1):
            if idx % progress_interval == 0 or idx == len(rids):
                progress = (idx / len(rids)) * 100
                logger.info(f"  ⏳ Progress: {idx}/{len(rids)} ({progress:.0f}%)")

            service_data = await get_service_details_by_rid(rid, credentials)

            if service_data and "serviceAttributesDetails" in service_data:
                locations = service_data.get("serviceAttributesDetails", {}).get("locations", [])

                if locations:
                    processed_count += 1

                    # Get delays for the specific origin and destination stations with cancellation reasons
                    dep_delay, arr_delay, dep_cancel_reason, arr_cancel_reason = get_station_delays(
                        locations, request.from_loc, request.to_loc
                    )

                    # Handle departure delays (including early, on-time, late, and cancelled)
                    if dep_delay is not None:
                        departure_delays.append(dep_delay)
                    elif dep_cancel_reason:
                        cancelled_departures += 1
                        cancellation_reasons["departure"].append(dep_cancel_reason)
                    else:
                        cancelled_departures += 1
                        cancellation_reasons["departure"].append("No data available")

                    # Handle arrival delays (including early, on-time, late, and cancelled)
                    if arr_delay is not None:
                        arrival_delays.append(arr_delay)
                    elif arr_cancel_reason:
                        cancelled_arrivals += 1
                        cancellation_reasons["arrival"].append(arr_cancel_reason)
                    else:
                        cancelled_arrivals += 1
                        cancellation_reasons["arrival"].append("No data available")
            else:
                logger.debug(f"⚠️  No detailed data for RID: {rid}")

        logger.info("-"*60)
        logger.info(f"✅ Successfully processed {processed_count}/{len(rids)} journeys")
        logger.info(f"📊 Departure data: {len(departure_delays)} with times, {cancelled_departures} cancelled")
        logger.info(f"📊 Arrival data: {len(arrival_delays)} with times, {cancelled_arrivals} cancelled")

        def create_enhanced_histogram(delays: List[int], cancelled_count: int = 0) -> Dict[str, Any]:
            """Create histogram with realistic train delay buckets as percentages"""
            # Calculate raw counts first
            counts = {}
            counts["3-5 min early"] = sum(1 for d in delays if -5 <= d <= -3)
            counts["2-3 min early"] = sum(1 for d in delays if -3 < d <= -2)
            counts["On time (±1 min)"] = sum(1 for d in delays if -1 <= d <= 1)
            counts["2-3 min late"] = sum(1 for d in delays if 1 < d <= 3)
            counts["3-5 min late"] = sum(1 for d in delays if 3 < d <= 5)
            counts["5-10 min late"] = sum(1 for d in delays if 5 < d <= 10)
            counts["10-15 min late"] = sum(1 for d in delays if 10 < d <= 15)
            counts["15-30 min late"] = sum(1 for d in delays if 15 < d <= 30)
            counts["30+ min late"] = sum(1 for d in delays if d > 30)
            if cancelled_count > 0:
                counts["Cancelled"] = cancelled_count

            # Calculate total for percentage calculation
            total_count = len(delays) + cancelled_count

            # Convert counts to percentages
            histogram = {}
            for bucket, count in counts.items():
                percentage = round((count / total_count) * 100, 1) if total_count > 0 else 0.0
                histogram[bucket] = percentage

            # Statistics - "on time" is ±1 minute
            on_time_count = sum(1 for d in delays if -1 <= d <= 1)
            early_count = sum(1 for d in delays if d < -1)
            late_count = sum(1 for d in delays if d > 1)
            extreme_delays = sum(1 for d in delays if d > 30)

            stats = {
                "avg_delay": round(sum(delays) / len(delays), 1) if delays else 0,
                "early_count": early_count,  # More than 1 min early
                "on_time_count": on_time_count,  # ±1 minute
                "late_count": late_count,  # More than 1 min late
                "extreme_delays": extreme_delays,  # >30 min late
                "cancelled_count": cancelled_count,
                "total_count": total_count,
                # Add percentage stats for easy access
                "on_time_percentage": round((on_time_count / total_count) * 100, 1) if total_count > 0 else 0.0,
                "early_percentage": round((early_count / total_count) * 100, 1) if total_count > 0 else 0.0,
                "late_percentage": round((late_count / total_count) * 100, 1) if total_count > 0 else 0.0,
                "cancelled_percentage": round((cancelled_count / total_count) * 100, 1) if total_count > 0 else 0.0
            }

            return {"histogram": histogram, "stats": stats, "raw_counts": counts}

        logger.info("📈 Generating enhanced histogram data...")

        departure_analysis = create_enhanced_histogram(departure_delays, cancelled_departures)
        arrival_analysis = create_enhanced_histogram(arrival_delays, cancelled_arrivals)

        # Get full station names
        from_station_name = get_station_name(request.from_loc)
        to_station_name = get_station_name(request.to_loc)

        # Create backward-compatible response structure for frontend
        result = {
            # New enhanced structure
            "route": f"{from_station_name} → {to_station_name}",
            "route_codes": f"{request.from_loc} → {request.to_loc}",
            "date_range": f"{request.from_date} to {request.to_date}",
            "time_range": f"{request.from_time} to {request.to_time}",
            "days": request.days,
            "total_services": len(services),
            "analyzed_services": processed_count,
            "rids_processed": len(rids),

            # Backward-compatible fields for frontend
            "departure_delays": {
                "histogram": departure_analysis["histogram"],
                "avg_delay": departure_analysis["stats"]["avg_delay"],
                "on_time_count": departure_analysis["stats"]["on_time_count"],  # Early to +5 min late
                "extreme_delays": sum(1 for d in departure_delays if d > 30)
            },
            "arrival_delays": {
                "histogram": arrival_analysis["histogram"],
                "avg_delay": arrival_analysis["stats"]["avg_delay"],
                "on_time_count": arrival_analysis["stats"]["on_time_count"],  # Early to +5 min late
                "extreme_delays": sum(1 for d in arrival_delays if d > 30)
            },

            # Enhanced performance data
            "departure_performance": {
                **departure_analysis,
                "cancelled_count": cancelled_departures,
                "cancellation_reasons": cancellation_reasons["departure"],
                "reliability": round((len(departure_delays) / (len(departure_delays) + cancelled_departures)) * 100, 1) if (len(departure_delays) + cancelled_departures) > 0 else 0
            },
            "arrival_performance": {
                **arrival_analysis,
                "cancelled_count": cancelled_arrivals,
                "cancellation_reasons": cancellation_reasons["arrival"],
                "reliability": round((len(arrival_delays) / (len(arrival_delays) + cancelled_arrivals)) * 100, 1) if (len(arrival_delays) + cancelled_arrivals) > 0 else 0
            }
        }

        logger.info("="*60)
        logger.info("🎉 JOURNEY ANALYSIS COMPLETED SUCCESSFULLY!")
        logger.info(f"📊 Average Departure Delay: {departure_analysis['stats']['avg_delay']} minutes")
        logger.info(f"📊 Average Arrival Delay: {arrival_analysis['stats']['avg_delay']} minutes")
        logger.info(f"✅ Departure Performance: {departure_analysis['stats']['early_count']} early, {departure_analysis['stats']['on_time_count']} on-time, {departure_analysis['stats']['late_count']} late, {cancelled_departures} cancelled")
        logger.info(f"✅ Arrival Performance: {arrival_analysis['stats']['early_count']} early, {arrival_analysis['stats']['on_time_count']} on-time, {arrival_analysis['stats']['late_count']} late, {cancelled_arrivals} cancelled")
        logger.info(f"🎯 Service Reliability: Departures {result['departure_performance']['reliability']}%, Arrivals {result['arrival_performance']['reliability']}%")
        logger.info("="*60)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating journey analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating journey analysis: {str(e)}")

@app.post("/api/v1/journey-analysis-stream")
async def analyze_journey_stream(request: ServiceMetricsRequest):
    """Get streaming journey analysis with real-time progress updates"""

    async def generate_progress():
        try:
            yield f"data: {json.dumps({'type': 'progress', 'step': 'initializing', 'message': 'Starting journey analysis...'})}\n\n"
            await asyncio.sleep(0.1)

            credentials = HSPCredentials(email=settings.RAIL_EMAIL, password=settings.RAIL_PWORD)

            yield f"data: {json.dumps({'type': 'progress', 'step': 'fetching_metrics', 'message': 'Fetching service metrics...'})}\n\n"
            await asyncio.sleep(0.1)

            # Get service metrics data for the specified route and date range
            metrics_data = await get_service_metrics(request, credentials)

            if not metrics_data or "Services" not in metrics_data:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No service data found for the specified route and date range'})}\n\n"
                return

            services = metrics_data["Services"]
            yield f"data: {json.dumps({'type': 'progress', 'step': 'extracting_rids', 'message': f'Found {len(services)} service patterns to analyze'})}\n\n"
            await asyncio.sleep(0.1)

            # Extract RIDs from services
            rids = []
            for i, service in enumerate(services, 1):
                if isinstance(service, dict) and "serviceAttributesMetrics" in service:
                    service_rids = service["serviceAttributesMetrics"].get("rids", [])
                    if service_rids:
                        rids.extend(service_rids)

            total_rids = len(rids)
            yield f"data: {json.dumps({'type': 'progress', 'step': 'processing_journeys', 'message': f'Processing {total_rids} individual journeys...', 'total': total_rids, 'current': 0})}\n\n"
            await asyncio.sleep(0.1)

            departure_delays = []
            arrival_delays = []
            cancelled_departures = 0
            cancelled_arrivals = 0
            cancellation_reasons = {"departure": [], "arrival": []}
            processed_count = 0

            # Process each RID with progress updates
            for idx, rid in enumerate(rids, 1):
                service_data = await get_service_details_by_rid(rid, credentials)

                if service_data and "serviceAttributesDetails" in service_data:
                    locations = service_data.get("serviceAttributesDetails", {}).get("locations", [])

                    if locations:
                        processed_count += 1

                        # Get delays for the specific origin and destination stations
                        dep_delay, arr_delay, dep_cancel_reason, arr_cancel_reason = get_station_delays(
                            locations, request.from_loc, request.to_loc
                        )

                        # Handle departure delays
                        if dep_delay is not None:
                            departure_delays.append(dep_delay)
                        elif dep_cancel_reason:
                            cancelled_departures += 1
                            cancellation_reasons["departure"].append(dep_cancel_reason)
                        else:
                            cancelled_departures += 1
                            cancellation_reasons["departure"].append("No data available")

                        # Handle arrival delays
                        if arr_delay is not None:
                            arrival_delays.append(arr_delay)
                        elif arr_cancel_reason:
                            cancelled_arrivals += 1
                            cancellation_reasons["arrival"].append(arr_cancel_reason)
                        else:
                            cancelled_arrivals += 1
                            cancellation_reasons["arrival"].append("No data available")

                # Send progress updates every 5% or for last item
                if idx % max(1, total_rids // 20) == 0 or idx == total_rids:
                    progress = (idx / total_rids) * 100
                    yield f"data: {json.dumps({'type': 'progress', 'step': 'processing_journeys', 'message': f'Processed {idx}/{total_rids} journeys ({progress:.0f}%)', 'total': total_rids, 'current': idx, 'percentage': progress})}\n\n"
                    await asyncio.sleep(0.1)

            yield f"data: {json.dumps({'type': 'progress', 'step': 'generating_analysis', 'message': 'Generating analysis results...'})}\n\n"
            await asyncio.sleep(0.1)

            # Generate the analysis result (reuse the existing logic)
            def create_enhanced_histogram(delays: List[int], cancelled_count: int = 0) -> Dict[str, Any]:
                counts = {}
                counts["3-5 min early"] = sum(1 for d in delays if -5 <= d <= -3)
                counts["2-3 min early"] = sum(1 for d in delays if -3 < d <= -2)
                counts["On time (±1 min)"] = sum(1 for d in delays if -1 <= d <= 1)
                counts["2-3 min late"] = sum(1 for d in delays if 1 < d <= 3)
                counts["3-5 min late"] = sum(1 for d in delays if 3 < d <= 5)
                counts["5-10 min late"] = sum(1 for d in delays if 5 < d <= 10)
                counts["10-15 min late"] = sum(1 for d in delays if 10 < d <= 15)
                counts["15-30 min late"] = sum(1 for d in delays if 15 < d <= 30)
                counts["30+ min late"] = sum(1 for d in delays if d > 30)
                if cancelled_count > 0:
                    counts["Cancelled"] = cancelled_count

                total_count = len(delays) + cancelled_count
                histogram = {}
                for bucket, count in counts.items():
                    percentage = round((count / total_count) * 100, 1) if total_count > 0 else 0.0
                    histogram[bucket] = percentage

                on_time_count = sum(1 for d in delays if -1 <= d <= 1)
                early_count = sum(1 for d in delays if d < -1)
                late_count = sum(1 for d in delays if d > 1)
                extreme_delays = sum(1 for d in delays if d > 30)

                stats = {
                    "avg_delay": round(sum(delays) / len(delays), 1) if delays else 0,
                    "early_count": early_count,
                    "on_time_count": on_time_count,
                    "late_count": late_count,
                    "extreme_delays": extreme_delays,
                    "cancelled_count": cancelled_count,
                    "total_count": total_count,
                    "on_time_percentage": round((on_time_count / total_count) * 100, 1) if total_count > 0 else 0.0,
                    "early_percentage": round((early_count / total_count) * 100, 1) if total_count > 0 else 0.0,
                    "late_percentage": round((late_count / total_count) * 100, 1) if total_count > 0 else 0.0,
                    "cancelled_percentage": round((cancelled_count / total_count) * 100, 1) if total_count > 0 else 0.0
                }

                return {"histogram": histogram, "stats": stats, "raw_counts": counts}

            departure_analysis = create_enhanced_histogram(departure_delays, cancelled_departures)
            arrival_analysis = create_enhanced_histogram(arrival_delays, cancelled_arrivals)

            # Get full station names
            from_station_name = get_station_name(request.from_loc)
            to_station_name = get_station_name(request.to_loc)

            # Create final result
            result = {
                "route": f"{from_station_name} → {to_station_name}",
                "route_codes": f"{request.from_loc} → {request.to_loc}",
                "date_range": f"{request.from_date} to {request.to_date}",
                "time_range": f"{request.from_time} to {request.to_time}",
                "days": request.days,
                "total_services": len(services),
                "analyzed_services": processed_count,
                "rids_processed": len(rids),
                "departure_delays": {
                    "histogram": departure_analysis["histogram"],
                    "avg_delay": departure_analysis["stats"]["avg_delay"],
                    "on_time_count": departure_analysis["stats"]["on_time_count"],
                    "extreme_delays": sum(1 for d in departure_delays if d > 30)
                },
                "arrival_delays": {
                    "histogram": arrival_analysis["histogram"],
                    "avg_delay": arrival_analysis["stats"]["avg_delay"],
                    "on_time_count": arrival_analysis["stats"]["on_time_count"],
                    "extreme_delays": sum(1 for d in arrival_delays if d > 30)
                },
                "departure_performance": {
                    **departure_analysis,
                    "cancelled_count": cancelled_departures,
                    "cancellation_reasons": cancellation_reasons["departure"],
                    "reliability": round((len(departure_delays) / (len(departure_delays) + cancelled_departures)) * 100, 1) if (len(departure_delays) + cancelled_departures) > 0 else 0
                },
                "arrival_performance": {
                    **arrival_analysis,
                    "cancelled_count": cancelled_arrivals,
                    "cancellation_reasons": cancellation_reasons["arrival"],
                    "reliability": round((len(arrival_delays) / (len(arrival_delays) + cancelled_arrivals)) * 100, 1) if (len(arrival_delays) + cancelled_arrivals) > 0 else 0
                }
            }

            yield f"data: {json.dumps({'type': 'complete', 'data': result})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Error generating journey analysis: {str(e)}'})}\n\n"

    return StreamingResponse(generate_progress(), media_type="text/plain")

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
async def get_ai_analysis(request: ServiceMetricsRequest):
    """Get AI analysis of delay patterns and predictions for any route"""
    try:
        logger.info(f"AI Analysis request received: {request}")

        # Get journey analysis data for the requested route
        journey_data = await analyze_journey(request)

        # Check if AI analysis is disabled in production
        if IS_PRODUCTION:
            return {
                "journey_data": journey_data,
                "ai_analysis": "AI analysis is disabled in production environment. The journey analysis data above provides detailed performance metrics for your route.",
                "generated_at": datetime.now().isoformat()
            }

        # Initialize OpenAI client
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

        # Extract key metrics for AI analysis
        dep_performance = journey_data.get('departure_performance', {})
        arr_performance = journey_data.get('arrival_performance', {})

        dep_stats = dep_performance.get('stats', {})
        arr_stats = arr_performance.get('stats', {})

        # Prepare data for AI analysis
        analysis_prompt = f"""
        You are a railway performance analyst. Analyze the following delay data for the {journey_data['route']} railway route and provide insights:

        Route: {journey_data['route']}
        Date Range: {journey_data['date_range']}
        Time Window: {journey_data['time_range']}
        Days: {journey_data['days']}
        Total Services Analyzed: {journey_data['analyzed_services']}

        Departure Performance:
        - Average Delay: {dep_stats.get('avg_delay', 0):.1f} minutes
        - On-time Rate: {dep_stats.get('on_time_percentage', 0):.1f}%
        - Early Rate: {dep_stats.get('early_percentage', 0):.1f}%
        - Late Rate: {dep_stats.get('late_percentage', 0):.1f}%
        - Cancelled Rate: {dep_stats.get('cancelled_percentage', 0):.1f}%
        - Reliability: {dep_performance.get('reliability', 0):.1f}%

        Arrival Performance:
        - Average Delay: {arr_stats.get('avg_delay', 0):.1f} minutes
        - On-time Rate: {arr_stats.get('on_time_percentage', 0):.1f}%
        - Early Rate: {arr_stats.get('early_percentage', 0):.1f}%
        - Late Rate: {arr_stats.get('late_percentage', 0):.1f}%
        - Cancelled Rate: {arr_stats.get('cancelled_percentage', 0):.1f}%
        - Reliability: {arr_performance.get('reliability', 0):.1f}%

        Please provide:
        1. Overall performance assessment (excellent/good/average/poor)
        2. Key delay patterns and reliability insights
        3. Probability of delays for future journeys (as a percentage)
        4. Expected delay range for a typical journey
        5. Recommendations for travelers
        6. Best travel tips based on this route's performance

        Keep your response concise but informative, suitable for a passenger planning their journey.
        """

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert railway analyst providing travel advice based on historical performance data."},
                {"role": "user", "content": analysis_prompt}
            ],
            max_tokens=600,
            temperature=0.7
        )

        ai_analysis = response.choices[0].message.content

        return {
            "journey_data": journey_data,
            "ai_analysis": ai_analysis,
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error generating AI analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating AI analysis: {str(e)}")

# Cache accessor endpoints
@app.get("/api/v1/cache/stats")
async def get_cache_stats():
    """Get cache statistics and overview"""
    return cache_manager.get_cache_stats()

@app.get("/api/v1/cache/metrics")
async def get_all_cached_metrics():
    """Get all cached metrics keyed by RID"""
    return cache_manager.get_all_metrics()

@app.get("/api/v1/cache/metrics/{rid}")
async def get_cached_metrics_by_rid(rid: str):
    """Get cached metrics for a specific RID"""
    metrics = cache_manager.get_metrics_by_rid(rid)
    if not metrics:
        raise HTTPException(status_code=404, detail=f"No metrics found for RID: {rid}")
    return metrics

@app.get("/api/v1/cache/services")
async def list_cached_services():
    """List all cached service files"""
    files = cache_manager.list_service_files()
    return {"service_files": files, "count": len(files)}

@app.get("/api/v1/cache/services/{filename}")
async def get_cached_service_by_filename(filename: str):
    """Get cached service data by filename"""
    service_data = cache_manager.get_service_by_filename(filename)
    if not service_data:
        raise HTTPException(status_code=404, detail=f"Service file not found: {filename}")
    return service_data

@app.get("/api/v1/cache/search")
async def search_cached_services(from_loc: str, to_loc: str):
    """Search cached services by route"""
    results = cache_manager.search_services_by_route(from_loc, to_loc)
    return {"route": f"{from_loc} → {to_loc}", "results": results, "count": len(results)}

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚄 TRELAY BACKEND SERVER STARTING UP")
    print("="*60)
    print("📍 Railway Journey Analysis API")
    print("🔧 FastAPI + Railway Data Integration")
    print("🌐 Server: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    print("-"*60)
    print("📡 Available Endpoints:")
    print("  • GET  /health - Health check")
    print("  • POST /api/v1/journey-analysis - Dynamic journey analysis")
    print("  • GET  /api/v1/delays/histogram - Demo data (PAD→HAV)")
    print("  • POST /api/v1/ai-analysis - AI analysis with OpenAI")
    print("  • GET  /api/v1/cache/stats - Cache statistics (SQLite)")
    print("  • GET  /api/v1/cache/metrics - All cached metrics (by RID)")
    print("  • GET  /api/v1/cache/services - List cached service requests")
    print("="*60)
    print("🚀 Starting server...")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
