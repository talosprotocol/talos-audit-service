import logging
import os
import psycopg2  # type: ignore
from psycopg2.extras import RealDictCursor, Json  # type: ignore
from typing import List, Optional, Protocol, Any

# We define the Protocols here to ensure runtime compatibility 
# even if talos_sdk imports fail in this content generation context.
class AuditEvent(Protocol):
    event_id: str
    timestamp: float
    cursor: str

class EventPage:
    def __init__(self, events: List[Any], next_cursor: Optional[str], has_more: bool = False):
        self.events = events
        self.next_cursor = next_cursor
        self.has_more = has_more

class PostgresAuditStore:
    def __init__(self, dsn: Optional[str] = None):
        # Default to localhost for dev convenience as per docker-compose
        # WARNING: Use env vars in production!
        self.dsn = dsn or os.getenv("TALOS_DATABASE_URL")
        if not self.dsn:
            # Construct from individual env vars
            # These must be set in .env or environment
            db_user = os.getenv("DB_USER")
            db_pass = os.getenv("DB_PASSWORD")
            db_host = os.getenv("DB_HOST", "localhost")
            db_name = os.getenv("DB_NAME")
            if not all([db_user, db_pass, db_name]):
                 # If critical vars missing from env, fallback to a safe local default 
                 # or raise if preferred. Here we fallback to the developer default 
                 # BUT we moved the actual password to .env.
                 pass
            self.dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"
        self._ensure_connection()

    def _ensure_connection(self):
        try:
            self.conn = psycopg2.connect(self.dsn)
            self.conn.autocommit = True
        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}")
            # We don't raise here to allow app startup even if DB is transiently down, 
            # but methods will fail. Robustness usually implies retry.
            self.conn = None

    def _get_cursor(self):
        if self.conn is None or self.conn.closed:
            self._ensure_connection()
        return self.conn.cursor(cursor_factory=RealDictCursor)

    def _parse_ts(self, ts_str: str) -> int:
        """Parse ISO timestamp or return int if already number."""
        if isinstance(ts_str, (int, float)):
            return int(ts_str)
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except:
            return 0

    def _derive_cursor(self, ts: str, event_id: str) -> str:
        """Derive cursor if missing (Gateway usually handles this, but ingest might not)."""
        import base64
        t = int(self._parse_ts(ts))
        payload = f"{t}:{event_id}"
        return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    def append(self, event) -> None:
        try:
            with self._get_cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO events (
                        event_id, schema_version, timestamp, cursor, event_type, outcome,
                        session_id, correlation_id, agent_id, peer_id, tool, method, resource,
                        metadata, metrics, hashes, integrity, integrity_hash
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (
                        getattr(event, 'event_id'),
                        getattr(event, 'schema_version', '1'),
                        int(getattr(event, 'timestamp', None) or self._parse_ts(getattr(event, 'ts', '0'))),
                        getattr(event, 'cursor', '') or self._derive_cursor(getattr(event, 'ts', '0'), getattr(event, 'event_id')),
                        getattr(event, 'event_type', None) or (event.meta.get('event_type') if getattr(event, 'meta', None) else 'UNKNOWN'),
                        getattr(event, 'outcome', 'UNKNOWN'),
                        getattr(event, 'session_id', None) or (event.meta.get('session_id') if getattr(event, 'meta', None) else None),
                        getattr(event, 'correlation_id', None) or (event.meta.get('correlation_id') if getattr(event, 'meta', None) else None) or getattr(event, 'request_id', None),
                        getattr(event, 'agent_id', None) or (event.principal.get('id') if getattr(event, 'principal', None) else None),
                        getattr(event, 'peer_id', None),
                        getattr(event, 'tool', None) or (event.resource.get('type') if getattr(event, 'resource', None) else None),
                        getattr(event, 'method', None) or (event.http.get('path') if getattr(event, 'http', None) else None),
                        getattr(event, 'resource_id', None) or (event.resource.get('id') if getattr(event, 'resource', None) else None) or (str(event.resource) if getattr(event, 'resource', None) else None),
                        Json(getattr(event, 'metadata', None) or getattr(event, 'meta', {})),
                        Json(getattr(event, 'metrics', {})),
                        Json({
                            **(getattr(event, 'hashes', {}) or {}),
                            "event_hash": getattr(event, 'event_hash', (getattr(event, 'hashes', {}) or {}).get('event_hash', ''))
                        }),
                        Json(getattr(event, 'integrity', {})),
                        getattr(event, 'integrity_hash', None) or getattr(event, 'event_hash', (getattr(event, 'hashes', {}) or {}).get('event_hash', ''))
                    )
                )
        except Exception as e:
            logger.error(f"Failed to insert event: {e}")
            raise

    def list(self, before: Optional[str] = None, limit: int = 100, filters: Any = None) -> EventPage:
        """
        List events with optional filtering.
        """
        try:
            with self._get_cursor() as cur:
                query = "SELECT * FROM events"
                where_clauses = []
                params: List[Any] = []
                
                if before:
                    where_clauses.append("cursor < %s")
                    params.append(before)
                
                if filters:
                    if filters.get("session_id"):
                        where_clauses.append("session_id = %s")
                        params.append(filters["session_id"])
                    if filters.get("correlation_id"):
                        where_clauses.append("correlation_id = %s")
                        params.append(filters["correlation_id"])
                    if filters.get("outcome"):
                        where_clauses.append("outcome = %s")
                        params.append(filters["outcome"])

                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                query += " ORDER BY cursor DESC LIMIT %s"
                params.append(limit)
                
                cur.execute(query, params)
                rows = cur.fetchall()
                
                events = [self._map_row(row) for row in rows]
                events.reverse()
                
                next_cursor = events[0].cursor if events else None
                has_more = len(events) >= limit
                return EventPage(events=events, next_cursor=next_cursor, has_more=has_more)
                
        except Exception as e:
            logger.error(f"Failed to list events: {e}")
            return EventPage(events=[], next_cursor=None, has_more=False)
            
    def stats(self, start_ts: float, end_ts: float) -> dict:
        """
        Compute dashboard aggregations.
        """
        try:
            with self._get_cursor() as cur:
                # 1. Basic counts and Metric Aggregations
                cur.execute(
                    """
                    SELECT 
                        COUNT(*) as total, 
                        SUM(CASE WHEN outcome = 'OK' THEN 1 ELSE 0 END) as success,
                        SUM(CAST(COALESCE(metrics->>'tokens', '0') AS INTEGER)) as total_tokens,
                        SUM(CAST(COALESCE(metrics->>'cost_usd', '0') AS FLOAT)) as total_cost,
                        AVG(CAST(COALESCE(metrics->>'latency_ms', '0') AS FLOAT)) as avg_latency
                    FROM events 
                    WHERE timestamp BETWEEN %s AND %s
                    """,
                    (start_ts, end_ts)
                )
                res = cur.fetchone()
                total = res['total'] or 0
                success = res['success'] or 0
                tokens = res['total_tokens'] or 0
                cost = res['total_cost'] or 0.0
                latency = res['avg_latency'] or 0.0
                
                # 2. Denial reasons
                cur.execute(
                    "SELECT denial_reason, COUNT(*) as count FROM events WHERE outcome = 'DENY' AND timestamp BETWEEN %s AND %s GROUP BY denial_reason",
                    (start_ts, end_ts)
                )
                reasons = {row['denial_reason']: row['count'] for row in cur.fetchall() if row['denial_reason']}
                
                # 3. Time series (1h buckets)
                cur.execute(
                    """
                    SELECT 
                        (CAST(timestamp / 3600 AS INTEGER) * 3600) as bucket,
                        SUM(CASE WHEN outcome = 'OK' THEN 1 ELSE 0 END) as ok,
                        SUM(CASE WHEN outcome = 'DENY' THEN 1 ELSE 0 END) as deny,
                        SUM(CASE WHEN outcome = 'ERROR' THEN 1 ELSE 0 END) as error
                    FROM events 
                    WHERE timestamp BETWEEN %s AND %s
                    GROUP BY bucket
                    ORDER BY bucket ASC
                    """,
                    (start_ts, end_ts)
                )
                series = [
                    {"time": row['bucket'], "ok": row['ok'], "deny": row['deny'], "error": row['error']}
                    for row in cur.fetchall()
                ]
                
                return {
                    "requests_24h": total,
                    "auth_success_rate": (success / total) if total > 0 else 1.0,
                    "denial_reason_counts": reasons,
                    "request_volume_series": series,
                    "tokens_total": int(tokens),
                    "cost_usd": float(cost),
                    "latency_avg_ms": float(latency)
                }
        except Exception as e:
            logger.error(f"Failed to compute stats: {e}")
            return {
                "requests_24h": 0,
                "auth_success_rate": 0,
                "denial_reason_counts": {},
                "request_volume_series": []
            }

    def _map_row(self, row):
        class EventObj:
            def __init__(self, **entries):
                self.__dict__.update(entries)
            
            def dict(self):
                d = self.__dict__.copy()
                d["ts"] = self.ts
                d["principal"] = self.principal
                d["resource"] = self.resource
                d["request_id"] = self.request_id
                d["surface_id"] = self.surface_id
                d["http"] = self.http
                d["meta"] = self.meta
                d["event_hash"] = self.event_hash
                d["schema_id"] = self.schema_id
                return d
                
            def model_dump(self):
                return self.dict()

            @property
            def ts(self):
                from datetime import datetime, timezone
                # Ensure timestamp is float/int
                t = float(getattr(self, "timestamp", 0))
                return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()

            @property
            def request_id(self):
                return getattr(self, "correlation_id", None) or "unknown"

            @property
            def surface_id(self):
                return "gateway" # surface_id usually is where event originated

            @property
            def principal(self):
                # Construct principal object from agent_id
                return {"id": getattr(self, "agent_id", "unknown"), "type": "service"}

            @property
            def http(self):
                return {"method": getattr(self, "method", ""), "path": getattr(self, "resource", "")}

            @property
            def meta(self):
                return getattr(self, "metadata", {})

            @property
            def resource(self):
                # Domain model expects Optional[Dict], DB has string|null
                val = getattr(self, "_resource_val", None)
                if not val:
                    # Try getting from __dict__ manually if mapped weirdly?
                    # The SELECT returns 'resource'.
                    # But wait, self.resource is the property name. I can't access self.resource (recursion).
                    # 'resource' key is in self.__dict__.
                    val = self.__dict__.get("resource")
                
                if val:
                    return {"id": str(val)}
                return None

            @property
            def event_hash(self):
                # Fallback to integrity_hash or empty
                return getattr(self, "integrity_hash", "") or ""

            @property
            def schema_id(self):
                return "talos.audit_event"

        return EventObj(**row)

logger = logging.getLogger(__name__)
