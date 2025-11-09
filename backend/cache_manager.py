import sqlite3
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging
import os

logger = logging.getLogger(__name__)

class CacheManager:
    """Manages logging/caching of service requests and metrics using SQLite with 300 MB size limit"""

    def __init__(self, base_path: str = "logs", max_cache_size_mb: int = 300):
        self.base_path = Path(base_path)
        self.db_path = self.base_path / "railway_cache.db"
        self.max_cache_size_bytes = max_cache_size_mb * 1024 * 1024  # Convert MB to bytes

        # Create directories
        os.makedirs(self.base_path, exist_ok=True)

        # Initialize SQLite database
        self._init_database()
        logger.info(f"Cache initialized with {max_cache_size_mb} MB size limit")
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Metrics table - RID is primary key (no timestamp needed - historical data)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS metrics (
                        rid TEXT PRIMARY KEY,
                        duration_ms INTEGER,
                        endpoint TEXT,
                        status_code INTEGER,
                        request_size INTEGER,
                        response_size INTEGER,
                        route TEXT,
                        services_count INTEGER,
                        error TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Service requests table - Full request/response data
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS service_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        rid TEXT NOT NULL,
                        service_name TEXT NOT NULL,
                        request_json TEXT NOT NULL,
                        response_json TEXT NOT NULL,
                        request_size INTEGER,
                        response_size INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (rid) REFERENCES metrics (rid)
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_route ON metrics(route)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_endpoint ON metrics(endpoint)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_requests_rid ON service_requests(rid)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_service_requests_service_name ON service_requests(service_name)")
                
                conn.commit()
                logger.info("SQLite database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    def generate_rid(self) -> str:
        """Generate a unique RID for caching purposes"""
        return f"RID_{uuid.uuid4().hex[:8]}"

    def _get_cache_size(self) -> int:
        """Get current cache size in bytes"""
        return self.db_path.stat().st_size if self.db_path.exists() else 0

    def _enforce_cache_limit(self):
        """Remove oldest entries if cache exceeds size limit"""
        try:
            current_size = self._get_cache_size()
            if current_size <= self.max_cache_size_bytes:
                return

            logger.info(f"Cache size ({current_size / (1024*1024):.2f} MB) exceeds limit ({self.max_cache_size_bytes / (1024*1024):.2f} MB). Cleaning up...")

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Delete oldest 20% of entries to make room
                # Delete from service_requests first (due to foreign key)
                cursor.execute("""
                    DELETE FROM service_requests
                    WHERE rid IN (
                        SELECT rid FROM metrics
                        ORDER BY created_at ASC
                        LIMIT (SELECT COUNT(*) * 0.2 FROM metrics)
                    )
                """)

                # Then delete from metrics
                cursor.execute("""
                    DELETE FROM metrics
                    WHERE rid IN (
                        SELECT rid FROM metrics
                        ORDER BY created_at ASC
                        LIMIT (SELECT COUNT(*) * 0.2 FROM metrics)
                    )
                """)

                conn.commit()

                # Vacuum to reclaim space
                cursor.execute("VACUUM")

                new_size = self._get_cache_size()
                logger.info(f"Cache cleaned. New size: {new_size / (1024*1024):.2f} MB")
        except Exception as e:
            logger.error(f"Failed to enforce cache limit: {e}")

    def cache_metrics(self, rid: str, metrics_data: Dict[str, Any]) -> str:
        """Cache metrics data keyed by RID"""
        try:
            self._enforce_cache_limit()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Insert or replace metrics (RID is historical, so no timestamp updates needed)
                cursor.execute("""
                    INSERT OR REPLACE INTO metrics
                    (rid, duration_ms, endpoint, status_code, request_size, response_size,
                     route, services_count, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rid,
                    metrics_data.get("duration_ms"),
                    metrics_data.get("endpoint"),
                    metrics_data.get("status_code", 200),
                    metrics_data.get("request_size"),
                    metrics_data.get("response_size"),
                    metrics_data.get("route"),
                    metrics_data.get("services_count"),
                    metrics_data.get("error")
                ))

                conn.commit()
                logger.info(f"Cached metrics for RID: {rid}")
                return rid
        except Exception as e:
            logger.error(f"Failed to cache metrics for RID {rid}: {e}")
            return rid
    
    def cache_service_request(self, service_name: str, request_data: Dict[str, Any],
                            response_data: Dict[str, Any], rid: str) -> str:
        """Cache detailed service request/response data"""
        try:
            self._enforce_cache_limit()
            request_json = json.dumps(request_data)
            response_json = json.dumps(response_data)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO service_requests 
                    (rid, service_name, request_json, response_json, request_size, response_size)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    rid,
                    service_name,
                    request_json,
                    response_json,
                    len(request_json),
                    len(response_json)
                ))
                
                conn.commit()
                logger.info(f"Cached service request: {service_name} (RID: {rid})")
                return str(cursor.lastrowid)
        except Exception as e:
            logger.error(f"Failed to cache service request {service_name}: {e}")
            return ""

    def get_cached_service_by_name(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve most recent cached service request/response by service_name"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM service_requests
                    WHERE service_name = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (service_name,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "rid": row["rid"],
                    "service_name": row["service_name"],
                    "timestamp": row["created_at"],
                    "request": json.loads(row["request_json"]),
                    "response": json.loads(row["response_json"]),
                    "metadata": {
                        "request_size": row["request_size"],
                        "response_size": row["response_size"],
                    },
                }
        except Exception as e:
            logger.error(f"Failed to get cached service by name {service_name}: {e}")
            return None
    
    def get_metrics_by_rid(self, rid: str) -> Optional[Dict[str, Any]]:
        """Retrieve metrics data by RID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM metrics WHERE rid = ?", (rid,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
        except Exception as e:
            logger.error(f"Failed to get metrics for RID {rid}: {e}")
            return None
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all cached metrics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM metrics ORDER BY created_at DESC")
                rows = cursor.fetchall()
                
                return {row['rid']: dict(row) for row in rows}
        except Exception as e:
            logger.error(f"Failed to get all metrics: {e}")
            return {}
    
    def list_service_files(self) -> List[str]:
        """List all cached service files (returns service names for compatibility)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT DISTINCT service_name, COUNT(*) as count 
                    FROM service_requests 
                    GROUP BY service_name 
                    ORDER BY service_name
                """)
                rows = cursor.fetchall()
                
                return [f"{row[0]} ({row[1]} records)" for row in rows]
        except Exception as e:
            logger.error(f"Failed to list service files: {e}")
            return []
    
    def get_service_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Get cached service data by service name (adapted from filename)"""
        try:
            # Extract service name from filename format
            service_name = filename.split('(')[0].strip() if '(' in filename else filename
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM service_requests 
                    WHERE service_name = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (service_name,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        "rid": row['rid'],
                        "service_name": row['service_name'],
                        "timestamp": row['created_at'],
                        "request": json.loads(row['request_json']),
                        "response": json.loads(row['response_json']),
                        "metadata": {
                            "request_size": row['request_size'],
                            "response_size": row['response_size']
                        }
                    }
                return None
        except Exception as e:
            logger.error(f"Failed to get service file {filename}: {e}")
            return None
    
    def search_services_by_route(self, from_loc: str, to_loc: str) -> List[Dict[str, Any]]:
        """Search cached services by route"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Search in service requests where request JSON contains the route
                cursor.execute("""
                    SELECT * FROM service_requests 
                    WHERE request_json LIKE ? AND request_json LIKE ?
                    ORDER BY created_at DESC
                """, (f'%"from_loc": "{from_loc}"%', f'%"to_loc": "{to_loc}"%'))
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    try:
                        results.append({
                            "rid": row['rid'],
                            "service_name": row['service_name'],
                            "timestamp": row['created_at'],
                            "request": json.loads(row['request_json']),
                            "response": json.loads(row['response_json']),
                            "metadata": {
                                "request_size": row['request_size'],
                                "response_size": row['response_size']
                            }
                        })
                    except json.JSONDecodeError:
                        continue
                
                return results
        except Exception as e:
            logger.error(f"Failed to search services by route {from_loc}->{to_loc}: {e}")
            return []
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get metrics count
                cursor.execute("SELECT COUNT(*) FROM metrics")
                metrics_count = cursor.fetchone()[0]
                
                # Get service requests count
                cursor.execute("SELECT COUNT(*) FROM service_requests")
                service_requests_count = cursor.fetchone()[0]
                
                # Get database file size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                
                # Get recent activity
                cursor.execute("""
                    SELECT COUNT(*) FROM metrics 
                    WHERE created_at > datetime('now', '-24 hours')
                """)
                recent_metrics = cursor.fetchone()[0]
                
                return {
                    "metrics_count": metrics_count,
                    "service_requests_count": service_requests_count,
                    "recent_metrics_24h": recent_metrics,
                    "total_cache_size_bytes": db_size,
                    "total_cache_size_mb": round(db_size / (1024 * 1024), 2),
                    "max_cache_size_mb": round(self.max_cache_size_bytes / (1024 * 1024), 2),
                    "cache_usage_percent": round((db_size / self.max_cache_size_bytes) * 100, 2),
                    "database_path": str(self.db_path),
                    "storage_type": "SQLite"
                }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}

# Global cache instance
cache_manager = CacheManager()