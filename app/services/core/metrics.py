from prometheus_client import Counter, Histogram

AUDIT_REQUESTS_TOTAL = Counter(
    "audit_requests_total", "Total audit requests received."
)

AUDIT_LATENCY_SECONDS = Histogram(
    "audit_latency_seconds",
    "Latency of audit pipeline in seconds.",
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10),
)

JUDGE_FAILURES_TOTAL = Counter(
    "judge_failures_total", "Count of judge fallbacks due to invalid responses."
)

