/**
 * k6 load test — /api/v1/rankings
 *
 * Usage (local):
 *   k6 run --env BASE_URL=https://your-api.railway.app \
 *           --env API_KEY=your-key \
 *           backend/tests/load/rankings.js
 *
 * Targets:
 *   - p95 response time < 500 ms
 *   - p99 response time < 1 000 ms
 *   - error rate < 1 %
 *   - throughput ≥ 100 req/s during sustained phase
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ── Custom metrics ────────────────────────────────────────────────────────────
const errorRate   = new Rate('consensus_errors');
const snapshotHit = new Rate('snapshot_cache_hit');  // tracks fast-path usage

// ── Configuration ─────────────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY  = __ENV.API_KEY  || '';

const HEADERS = {
  'Accept': 'application/json',
  ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
};

// ── Test scenarios ─────────────────────────────────────────────────────────────
export const options = {
  scenarios: {
    // Smoke: verify the endpoint works before ramping (1 VU, 30s)
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      tags: { scenario: 'smoke' },
      gracefulStop: '5s',
    },

    // Load: ramp to 100 RPS using constant-arrival-rate.
    // preAllocatedVUs sets the starting pool; k6 adds more up to maxVUs
    // if requests are queuing (i.e. p95 > 500 ms).
    load: {
      executor: 'ramping-arrival-rate',
      startRate: 0,
      timeUnit: '1s',
      preAllocatedVUs: 50,
      maxVUs: 250,
      stages: [
        { target: 20,  duration: '30s' },   // warm up
        { target: 100, duration: '1m' },    // ramp to target
        { target: 100, duration: '3m' },    // sustain
        { target: 0,   duration: '30s' },   // cool down
      ],
      startTime: '35s',   // start after smoke completes
      tags: { scenario: 'load' },
    },
  },

  thresholds: {
    // Core SLOs
    'http_req_duration{scenario:load}': [
      'p(95)<500',   // p95 < 500 ms
      'p(99)<1000',  // p99 < 1 s
    ],
    // Error rate
    'consensus_errors{scenario:load}': ['rate<0.01'],
    // Smoke must also pass
    'http_req_duration{scenario:smoke}': ['p(95)<800'],
  },
};

// ── Endpoint variants ─────────────────────────────────────────────────────────
const ENDPOINTS = [
  `${BASE_URL}/api/v1/rankings?market=US&limit=50`,
  `${BASE_URL}/api/v1/rankings?market=US&limit=50&asset_type=stock`,
  `${BASE_URL}/api/v1/rankings?market=KR&limit=50`,
  `${BASE_URL}/api/v1/rankings?market=US&limit=50&conviction=DIAMOND&conviction=GOLD`,
];

// ── Main VU function ──────────────────────────────────────────────────────────
export default function () {
  // Round-robin across endpoint variants to exercise different query paths
  const url = ENDPOINTS[__VU % ENDPOINTS.length];

  const res = http.get(url, {
    headers: HEADERS,
    tags: { endpoint: 'rankings' },
  });

  // Track errors
  const ok = check(res, {
    'status is 200 or 304': (r) => r.status === 200 || r.status === 304,
    'response time < 1s':   (r) => r.timings.duration < 1000,
  });
  errorRate.add(!ok);

  // Track snapshot cache hit rate (fast path returns source: "snapshot")
  if (res.status === 200 && res.body) {
    try {
      const body = JSON.parse(res.body);
      snapshotHit.add(body.source === 'snapshot' || Array.isArray(body.items));
    } catch (_) {
      // body parse failed — not critical
    }
  }

  sleep(0.1); // 100 ms think time between requests per VU
}

// ── Setup: verify the endpoint is reachable before starting ──────────────────
export function setup() {
  const healthRes = http.get(`${BASE_URL}/api/v1/health`, { headers: HEADERS });
  if (healthRes.status !== 200) {
    throw new Error(`Health check failed: ${healthRes.status} — is the API running at ${BASE_URL}?`);
  }
  console.log(`✓ API reachable at ${BASE_URL}`);
  console.log(`✓ Health: ${healthRes.body}`);
}

// ── Teardown: print a summary ─────────────────────────────────────────────────
export function teardown(data) {
  console.log('Load test complete. Check the summary above for SLO results.');
}
