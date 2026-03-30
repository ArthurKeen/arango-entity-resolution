"""GAE (Graph Analytics Engine) connection layer.

Supports two deployment modes, matching the conventions in ``agentic-graph-analytics``:

* **self_managed** -- authenticates via JWT obtained from ``/_open/auth``;
  engine lifecycle via ``/gen-ai/v1/graphanalytics``; engine API via
  ``/gral/<short_id>/v1/...``.
* **managed** (AMP) -- authenticates via ``oasisctl`` bearer token;
  management API on port 8829; engine API on a dynamic engine URL.

The factory ``get_gae_connection()`` reads ``TEST_DEPLOYMENT_MODE`` (or
``GAE_DEPLOYMENT_MODE``) from the environment and returns the right client.
"""

from __future__ import annotations

import logging
import os
import time
import warnings
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

DEFAULT_POLL_INTERVAL = 2
DEFAULT_JOB_TIMEOUT = 3600
DEFAULT_ENGINE_API_TIMEOUT = 30
DEFAULT_GAE_PORT = 8829
DEFAULT_ENGINE_API_RETRIES = 5
REQUIRED_CONSECUTIVE_OK = 3
API_VERSION_PREFIX = "v1/"

COMPLETED_STATES = frozenset({"done", "finished", "completed", "succeeded"})
FAILED_STATES = frozenset({"failed", "error", "cancelled"})

# Suppress urllib3 InsecureRequestWarning when the caller opts out of SSL
try:
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning as _InsecureWarn
except Exception:
    urllib3 = None  # type: ignore[assignment]
    _InsecureWarn = None  # type: ignore[assignment,misc]


# ── Helpers ──────────────────────────────────────────────────────────

def _parse_bool_env(name: str, default: bool = True) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes")


def _extract_deployment_url(endpoint: str) -> str:
    """Strip the port from an endpoint URL."""
    if "://" in endpoint:
        proto, rest = endpoint.split("://", 1)
        host = rest.split("/", 1)[0]
        if ":" in host:
            host = host.split(":", 1)[0]
        return f"{proto}://{host}"
    return endpoint.rsplit(":", 1)[0] if ":" in endpoint else endpoint


# ── Base class ───────────────────────────────────────────────────────

class GAEConnectionBase(ABC):
    """Abstract base for both self-managed and AMP GAE connections."""

    engine_id: Optional[str]

    @abstractmethod
    def deploy_engine(self, **kwargs) -> Dict[str, Any]:
        ...

    @abstractmethod
    def stop_engine(self, service_id: Optional[str] = None) -> bool:
        ...

    @abstractmethod
    def get_engine_version(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def load_graph(
        self,
        database: str,
        vertex_collections: List[str],
        edge_collections: List[str],
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def run_wcc(self, graph_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def store_results(
        self,
        target_collection: str,
        job_ids: List[str],
        attribute_names: List[str],
        database: str,
    ) -> Dict[str, Any]:
        ...

    @abstractmethod
    def get_job(self, job_id: str) -> Dict[str, Any]:
        ...

    def is_available(self) -> bool:
        """Lightweight probe -- can we talk to the platform at all?"""
        try:
            self.deploy_engine(reuse_existing=True)
            return True
        except Exception:
            return False

    # ── Shared polling helpers ───────────────────────────────────────

    def wait_for_job(
        self,
        job_id,
        timeout: int = DEFAULT_JOB_TIMEOUT,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> Dict[str, Any]:
        """Poll ``get_job`` until it finishes, fails, or times out."""
        deadline = time.time() + timeout
        interval = float(poll_interval)

        while time.time() < deadline:
            job = self.get_job(job_id)
            if not job:
                time.sleep(interval)
                continue

            status = (
                job.get("status")
                or job.get("state")
                or ("done" if job.get("progress") == job.get("total") and job.get("total") else None)
                or "unknown"
            )
            status_l = str(status).lower()

            if status_l in COMPLETED_STATES:
                return job
            if status_l in FAILED_STATES:
                raise RuntimeError(f"GAE job {job_id} failed: {job}")

            logger.debug("Job %s status=%s, polling...", job_id, status_l)
            remaining = deadline - time.time()
            time.sleep(min(interval, max(remaining, 0)))
            interval = min(interval * 1.25, 15.0)

        raise TimeoutError(
            f"GAE job {job_id} did not complete within {timeout}s"
        )

    def wait_for_engine_ready(
        self,
        max_retries: int = 60,
        retry_interval: int = 2,
    ) -> bool:
        """Wait for the GRAL engine API to be healthy (3 consecutive OK probes)."""
        consecutive_ok = 0
        for i in range(max_retries):
            try:
                self.get_engine_version()
                consecutive_ok += 1
                if consecutive_ok >= REQUIRED_CONSECUTIVE_OK:
                    logger.info("GAE engine API is ready")
                    time.sleep(2)
                    return True
            except Exception:
                consecutive_ok = 0
                if i % 5 == 0:
                    logger.info("Waiting for GAE engine API... (%d/%d)", i + 1, max_retries)
                time.sleep(retry_interval)
        raise TimeoutError(
            f"GAE engine API did not become ready after {max_retries * retry_interval}s"
        )


# ── Self-managed connection (GenAI / GRAL) ───────────────────────────

class SelfManagedGAEConnection(GAEConnectionBase):
    """GAE connection for self-managed ArangoDB with GenAI suite.

    Auth: JWT from ``/_open/auth``.
    Control plane: ``/gen-ai/v1/graphanalytics``.
    Engine API: ``/gral/<short_id>/v1/...``.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
        timeout: int = 300,
    ):
        self.endpoint = (endpoint or os.environ["ARANGO_ENDPOINT"]).rstrip("/")
        self.user = user or os.getenv("ARANGO_USER", "root")
        self.password = password or os.environ["ARANGO_PASSWORD"]
        self.database = database or os.getenv("ARANGO_DATABASE", "_system")
        self.timeout = int(os.getenv("ARANGO_TIMEOUT", str(timeout)))

        if verify_ssl is None:
            self.verify_ssl = _parse_bool_env("ARANGO_VERIFY_SSL", True)
        else:
            self.verify_ssl = verify_ssl

        if not self.verify_ssl:
            self._suppress_ssl_warnings()

        self.jwt_token: Optional[str] = None
        self.engine_id: Optional[str] = None

    # ── Auth ─────────────────────────────────────────────────────────

    def _suppress_ssl_warnings(self) -> None:
        if _InsecureWarn is not None:
            try:
                if urllib3 is not None:
                    urllib3.disable_warnings(_InsecureWarn)
                warnings.filterwarnings("ignore", category=_InsecureWarn)
            except Exception:
                pass

    def _get_jwt_token(self) -> str:
        url = f"{self.endpoint}/_open/auth"
        try:
            resp = requests.post(
                url,
                json={"username": self.user, "password": self.password},
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            resp.raise_for_status()
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 401:
                raise RuntimeError(
                    f"Authentication failed (401) at {url}.\n"
                    f"  User: {self.user}\n"
                    f"  Endpoint: {self.endpoint}\n"
                    f"  Check ARANGO_PASSWORD in your .env file."
                ) from exc
            raise
        token = resp.json().get("jwt")
        if not token:
            raise ValueError("No JWT token in ArangoDB auth response")
        self.jwt_token = token
        logger.info("JWT token obtained from %s", self.endpoint)
        return token

    def _get_headers(self) -> Dict[str, str]:
        if not self.jwt_token:
            self._get_jwt_token()
        return {
            "Authorization": f"bearer {self.jwt_token}",
            "Content-Type": "application/json",
        }

    def _refresh_jwt(self) -> None:
        self.jwt_token = None
        self._get_jwt_token()

    # ── Engine lifecycle ─────────────────────────────────────────────

    def _get_engine_url(self) -> str:
        if not self.engine_id:
            raise ValueError("No engine running. Call deploy_engine() first.")
        short_id = self.engine_id.split("-")[-1]
        return f"{self.endpoint}/gral/{short_id}"

    def deploy_engine(self, reuse_existing: bool = True, **kwargs) -> Dict[str, Any]:
        service_id = self._ensure_service(reuse_existing=reuse_existing)
        return {"id": service_id, "status": {"is_started": True, "succeeded": True}}

    def _ensure_service(self, reuse_existing: bool = True) -> str:
        if reuse_existing:
            logger.info("Checking for existing GAE services...")
            try:
                services = self._list_services()
                for svc in services:
                    sid = str(svc.get("serviceId", ""))
                    status = svc.get("status")
                    svc_type = svc.get("type")
                    if status != "DEPLOYED":
                        continue
                    if svc_type == "gral" or sid.startswith("arangodb-gral-"):
                    try:
                        self.engine_id = sid
                        self.get_engine_version()
                        logger.info("Reusing existing DEPLOYED service: %s", sid)
                        return sid
                    except Exception as e:
                        logger.debug("Service %s is DEPLOYED but engine API check failed: %s", sid, e)
                        continue
            except Exception as exc:
                logger.debug("Could not list services: %s", exc)

        logger.info("Starting new GAE service...")
        return self._start_engine()

    def _start_engine(self) -> str:
        url = f"{self.endpoint}/gen-ai/v1/graphanalytics"
        headers = self._get_headers()

        resp = requests.post(url, json={}, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
        if resp.status_code == 401:
            self._refresh_jwt()
            headers = self._get_headers()
            resp = requests.post(url, json={}, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
        resp.raise_for_status()

        service_info = resp.json().get("serviceInfo", {})
        service_id = service_info.get("serviceId")
        if not service_id or service_id == "null":
            raise RuntimeError(f"Failed to start GAE engine: {resp.json()}")

        self.engine_id = service_id
        logger.info("GAE engine started: %s", service_id)
        return service_id

    def stop_engine(self, service_id: Optional[str] = None) -> bool:
        service_id = service_id or self.engine_id
        if not service_id:
            return False

        url = f"{self.endpoint}/gen-ai/v1/service/{service_id}"
        headers = self._get_headers()
        try:
            resp = requests.delete(url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
            if resp.status_code == 401:
                self._refresh_jwt()
                headers = self._get_headers()
                resp = requests.delete(url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
            resp.raise_for_status()
        except requests.HTTPError as exc:
            body = (exc.response.text or "").lower() if exc.response is not None else ""
            if exc.response is not None and exc.response.status_code == 500 and "not found" in body:
                logger.info("Engine %s already stopped", service_id)
            else:
                raise
        if service_id == self.engine_id:
            self.engine_id = None
        logger.info("GAE engine stopped: %s", service_id)
        return True

    def _list_services(self) -> List[Dict[str, Any]]:
        url = f"{self.endpoint}/gen-ai/v1/list_services"
        headers = self._get_headers()
        resp = requests.post(url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
        if resp.status_code == 401:
            self._refresh_jwt()
            headers = self._get_headers()
            resp = requests.post(url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
        resp.raise_for_status()
        return resp.json().get("services", [])

    # ── Engine API calls ─────────────────────────────────────────────

    def _make_engine_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """HTTP call to the GRAL engine with retry for transient route errors."""
        if not self.engine_id:
            self._ensure_service()

        engine_url = self._get_engine_url()
        url = f"{engine_url}/{endpoint.lstrip('/')}"

        max_attempts = int(os.getenv("GAE_ENGINE_API_RETRIES", str(DEFAULT_ENGINE_API_RETRIES)))
        for attempt in range(1, max_attempts + 1):
            headers = self._get_headers()
            try:
                if method == "GET":
                    resp = requests.get(url, headers=headers, timeout=self.timeout, verify=self.verify_ssl)
                else:
                    resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout, verify=self.verify_ssl)

                if resp.status_code == 401 and attempt < max_attempts:
                    self._refresh_jwt()
                    continue

                if resp.status_code >= 400:
                    logger.error(
                        "Engine API %s %s returned %d: %s",
                        method, endpoint, resp.status_code, resp.text[:500],
                    )
                resp.raise_for_status()
                return resp.json() if resp.text else {}

            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                body = (exc.response.text or "").lower() if exc.response is not None else ""
                transient = (
                    status in (404, 503)
                    and ("unknown path '/gral/" in body or "upstream" in body or "connection refused" in body)
                )
                if transient and attempt < max_attempts:
                    logger.debug("Transient GRAL route error (attempt %d/%d), retrying...", attempt, max_attempts)
                    time.sleep(2)
                    continue
                raise

        return {}

    def get_engine_version(self) -> Dict[str, Any]:
        return self._make_engine_request("GET", f"{API_VERSION_PREFIX}version")

    def load_graph(
        self,
        database: str,
        vertex_collections: List[str],
        edge_collections: List[str],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "database": database,
            "vertex_collections": vertex_collections,
            "edge_collections": edge_collections,
        }
        job = self._make_engine_request("POST", f"{API_VERSION_PREFIX}loaddata", payload)
        return self._normalize_job(job)

    def run_wcc(self, graph_id: str) -> Dict[str, Any]:
        job = self._make_engine_request("POST", f"{API_VERSION_PREFIX}wcc", {"graph_id": graph_id})
        return self._normalize_job(job)

    def store_results(
        self,
        target_collection: str,
        job_ids: List[str],
        attribute_names: List[str],
        database: str,
        parallelism: int = 8,
        batch_size: int = 10_000,
    ) -> Dict[str, Any]:
        payload = {
            "database": database,
            "target_collection": target_collection,
            "job_ids": job_ids,
            "attribute_names": attribute_names,
            "parallelism": parallelism,
            "batch_size": batch_size,
        }
        job = self._make_engine_request("POST", f"{API_VERSION_PREFIX}storeresults", payload)
        return self._normalize_job(job)

    def get_job(self, job_id) -> Dict[str, Any]:
        try:
            return self._make_engine_request("GET", f"{API_VERSION_PREFIX}jobs/{job_id}")
        except Exception as e:
            logger.debug("Direct job fetch failed for %s, trying fallback: %s", job_id, e)
        # Fallback: list all jobs and filter
        try:
            resp = self._make_engine_request("GET", f"{API_VERSION_PREFIX}jobs")
            jobs = resp.get("jobs", [])
            job_id_str = str(job_id)
            for j in jobs:
                jid = j.get("job_id", j.get("id"))
                if str(jid) == job_id_str or jid == job_id:
                    return j
        except Exception as e:
            logger.debug("Fallback job list fetch also failed for %s: %s", job_id, e)
        return {}

    @staticmethod
    def _normalize_job(job: Dict[str, Any]) -> Dict[str, Any]:
        if "job_id" in job and "id" not in job:
            job["id"] = job["job_id"]
        return job


# ── AMP connection (Arango Managed Platform) ─────────────────────────

class AMPGAEConnection(GAEConnectionBase):
    """GAE connection for ArangoDB Managed Platform (AMP / ArangoGraph).

    Auth: oasisctl bearer token.
    Management API: ``<deployment_url>:<gae_port>/graph-analytics/api/graphanalytics/v1``.
    Engine API: dynamic URL from deployed engine record.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key_id: Optional[str] = None,
        api_key_secret: Optional[str] = None,
        database: Optional[str] = None,
        gae_port: Optional[int] = None,
    ):
        ep = (endpoint or os.environ["ARANGO_ENDPOINT"]).rstrip("/")
        self.deployment_url = _extract_deployment_url(ep)
        self.database = database or os.getenv("ARANGO_DATABASE", "_system")
        self.api_key_id = api_key_id or os.environ["ARANGO_GRAPH_API_KEY_ID"]
        self.api_key_secret = api_key_secret or os.environ["ARANGO_GRAPH_API_KEY_SECRET"]
        self.gae_port = gae_port or int(os.getenv("ARANGO_GAE_PORT", str(DEFAULT_GAE_PORT)))
        self.timeout = int(os.getenv("ARANGO_TIMEOUT", "300"))

        self.base_url = (
            f"{self.deployment_url}:{self.gae_port}"
            f"/graph-analytics/api/graphanalytics/v1"
        )

        self.access_token: Optional[str] = None
        self.engine_id: Optional[str] = None
        self.current_engine_url: Optional[str] = None

        self._initialize_token()

    # ── Token management ─────────────────────────────────────────────

    def _initialize_token(self) -> None:
        token = os.getenv("ARANGO_GRAPH_TOKEN", "").strip()
        if token:
            self.access_token = token
            return
        self._refresh_token()

    def _refresh_token(self) -> None:
        import subprocess
        try:
            result = subprocess.run(
                ["oasisctl", "login", "--key-id", self.api_key_id, "--key-secret", self.api_key_secret],
                capture_output=True, text=True, check=True, shell=False,
            )
            self.access_token = result.stdout.strip()
            if not self.access_token:
                raise RuntimeError("oasisctl returned empty token")
            logger.info("AMP token refreshed via oasisctl")
        except FileNotFoundError:
            raise RuntimeError(
                "oasisctl not found. Install it:\n"
                "  macOS: brew install arangodb/tap/oasisctl\n"
                "  https://github.com/arangodb-managed/oasisctl/releases"
            )

    def _mgmt_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _engine_headers(self) -> Dict[str, str]:
        return self._mgmt_headers()

    # ── Management API ───────────────────────────────────────────────

    def deploy_engine(self, size_id: str = "e8", reuse_existing: bool = True, **kwargs) -> Dict[str, Any]:
        if reuse_existing:
            engines = self._list_engines()
            for eng in engines:
                st = eng.get("status", {})
                if st.get("is_started") and st.get("succeeded"):
                    eid = eng.get("id")
                    eurl = st.get("url") or st.get("engine_url")
                    if eid and eurl:
                        self.engine_id = eid
                        self.current_engine_url = eurl.rstrip("/")
                        logger.info("Reusing AMP engine %s", eid)
                        return eng

        payload = {"size_id": size_id}
        resp = requests.post(
            f"{self.base_url}/engines", json=payload,
            headers=self._mgmt_headers(), timeout=self.timeout,
        )
        resp.raise_for_status()
        engine = resp.json()
        eid = engine.get("id")
        self.engine_id = eid

        engine = self._wait_for_engine_started(eid)
        st = engine.get("status", {})
        self.current_engine_url = (st.get("url") or st.get("engine_url", "")).rstrip("/")
        return engine

    def _list_engines(self) -> List[Dict[str, Any]]:
        resp = requests.get(
            f"{self.base_url}/engines", headers=self._mgmt_headers(), timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("items", [])

    def _wait_for_engine_started(self, engine_id: str, timeout: int = 120) -> Dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = requests.get(
                f"{self.base_url}/engines/{engine_id}",
                headers=self._mgmt_headers(), timeout=self.timeout,
            )
            resp.raise_for_status()
            engine = resp.json()
            st = engine.get("status", {})
            if st.get("is_started") and st.get("succeeded"):
                return engine
            time.sleep(2)
        raise TimeoutError(f"AMP engine {engine_id} did not start within {timeout}s")

    def stop_engine(self, service_id: Optional[str] = None) -> bool:
        eid = service_id or self.engine_id
        if not eid:
            return False
        resp = requests.delete(
            f"{self.base_url}/engines/{eid}",
            headers=self._mgmt_headers(), timeout=self.timeout,
        )
        resp.raise_for_status()
        if eid == self.engine_id:
            self.engine_id = None
            self.current_engine_url = None
        return True

    # ── Engine API ───────────────────────────────────────────────────

    def _engine_api_call(
        self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.current_engine_url:
            raise ValueError("No engine URL. Deploy an engine first.")
        url = f"{self.current_engine_url}/{endpoint.lstrip('/')}"
        headers = self._engine_headers()
        if method == "GET":
            resp = requests.get(url, headers=headers, timeout=self.timeout)
        else:
            resp = requests.post(url, headers=headers, json=data, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json() if resp.text else {}

    def get_engine_version(self) -> Dict[str, Any]:
        return self._engine_api_call("GET", f"{API_VERSION_PREFIX}version")

    def load_graph(
        self, database: str,
        vertex_collections: List[str], edge_collections: List[str],
    ) -> Dict[str, Any]:
        payload = {
            "database": database,
            "vertex_collections": vertex_collections,
            "edge_collections": edge_collections,
        }
        job = self._engine_api_call("POST", f"{API_VERSION_PREFIX}loaddata", payload)
        return self._normalize_job(job)

    def run_wcc(self, graph_id: str) -> Dict[str, Any]:
        job = self._engine_api_call("POST", f"{API_VERSION_PREFIX}wcc", {"graph_id": graph_id})
        return self._normalize_job(job)

    def store_results(
        self, target_collection: str, job_ids: List[str],
        attribute_names: List[str], database: str,
        parallelism: int = 8, batch_size: int = 10_000,
    ) -> Dict[str, Any]:
        payload = {
            "database": database,
            "target_collection": target_collection,
            "job_ids": job_ids,
            "attribute_names": attribute_names,
            "parallelism": parallelism,
            "batch_size": batch_size,
        }
        job = self._engine_api_call("POST", f"{API_VERSION_PREFIX}storeresults", payload)
        return self._normalize_job(job)

    def get_job(self, job_id: str) -> Dict[str, Any]:
        try:
            return self._engine_api_call("GET", f"{API_VERSION_PREFIX}jobs/{job_id}")
        except Exception as e:
            logger.debug("Direct job fetch failed for %s, trying fallback: %s", job_id, e)
        try:
            resp = self._engine_api_call("GET", f"{API_VERSION_PREFIX}jobs")
            for j in resp.get("jobs", []):
                if str(j.get("job_id", j.get("id"))) == str(job_id):
                    return j
        except Exception as e:
            logger.debug("Fallback job list fetch also failed for %s: %s", job_id, e)
        return {}

    @staticmethod
    def _normalize_job(job: Dict[str, Any]) -> Dict[str, Any]:
        if "job_id" in job and "id" not in job:
            job["id"] = job["job_id"]
        return job


# ── Factory ──────────────────────────────────────────────────────────

def get_gae_connection(
    deployment_mode: Optional[str] = None,
    **kwargs,
) -> GAEConnectionBase:
    """Return the appropriate GAE connection based on deployment mode.

    Reads ``TEST_DEPLOYMENT_MODE`` or ``GAE_DEPLOYMENT_MODE`` from the
    environment if *deployment_mode* is not provided.  Mapping:

    * ``self_managed_platform`` / ``self_managed`` / ``self-managed`` / ``genai``
      → :class:`SelfManagedGAEConnection`
    * ``managed_platform`` / ``amp`` / ``managed`` / ``arangograph``
      → :class:`AMPGAEConnection`
    """
    if deployment_mode is None:
        deployment_mode = (
            os.getenv("TEST_DEPLOYMENT_MODE")
            or os.getenv("GAE_DEPLOYMENT_MODE")
            or "self_managed"
        )

    mode = deployment_mode.strip().lower()

    self_managed_aliases = {"self_managed_platform", "self_managed", "self-managed", "genai", "gen-ai"}
    amp_aliases = {"managed_platform", "amp", "managed", "arangograph"}

    if mode in self_managed_aliases:
        return SelfManagedGAEConnection(**kwargs)
    if mode in amp_aliases:
        return AMPGAEConnection(**kwargs)

    raise ValueError(
        f"Unknown GAE deployment mode: {deployment_mode!r}. "
        f"Expected one of: {sorted(self_managed_aliases | amp_aliases)}"
    )
