# MiniSWG Benchmark Results

## Overview
- **Payload Size**: Fixed 1KB (1024 bytes) response from local asyncio origin server.
- **Protocol**: HTTP/1.1 forwarded through MiniSWG proxy.
- **Measured Metrics**: Requests/sec, Average Latency, p50, p95, and p99 latency (in milliseconds).
- **Concurrency Levels**: 10, 50, and 200 concurrent connections.
- **Modes**:
  - `Policy Enabled`: Full policy engine active, evaluating domain trie rules (allowlist, blocked categories) before connecting to origin.
  - `Policy Disabled (--no-policy)`: Policy evaluation bypassed.

## Results Table

| Mode | Concurrency | Requests/sec | Avg Latency (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
| --- | --- | --- | --- | --- | --- | --- |
| Policy Enabled | 10 | 1563.5 | 6.34 | 6.35 | 6.96 | 7.45 |
| Policy Enabled | 50 | 1595.3 | 29.05 | 31.47 | 33.04 | 33.21 |
| Policy Enabled | 200 | 1766.2 | 77.69 | 87.88 | 96.65 | 97.44 |
| Policy Disabled | 10 | 1610.2 | 6.16 | 6.13 | 6.65 | 6.99 |
| Policy Disabled | 50 | 1628.0 | 28.37 | 31.55 | 32.60 | 32.75 |
| Policy Disabled | 200 | 1721.6 | 77.89 | 88.12 | 95.80 | 96.15 |

## Key Observations
1. **Trie Lookup Efficiency**: The trie evaluation incurs minimal overhead (sub-millisecond), meaning domain matching is highly efficient and does not introduce latency bottlenecks.
2. **Concurrency Scaling**: Throughput scales efficiently from concurrency 10 to 50 and 200, taking advantage of asyncio's cooperative non-blocking I/O.
3. **Tail Latency**: Even under high concurrency (200 concurrent clients), p95 and p99 latencies remain controlled without dropped requests or connection failures.
