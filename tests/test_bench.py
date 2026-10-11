import asyncio
import os
import pytest
from bench.run_bench import (
    LocalOriginServer,
    calc_percentile,
    format_results_table,
    generate_markdown_report,
    run_suite,
    BenchmarkResult,
)


def test_calc_percentile():
    data = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert calc_percentile(data, 50.0) == 30.0
    assert calc_percentile(data, 0.0) == 10.0
    assert calc_percentile(data, 100.0) == 50.0
    assert calc_percentile([], 50.0) == 0.0


@pytest.mark.asyncio
async def test_local_origin_server_returns_1kb():
    origin = LocalOriginServer()
    port = await origin.start()
    assert port > 0

    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /test HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        await writer.drain()

        response = await reader.read()
        writer.close()
        await writer.wait_closed()

        assert b"HTTP/1.1 200 OK" in response
        assert b"Content-Length: 1024" in response
        assert response.endswith(b"X" * 1024)
    finally:
        await origin.stop()


def test_format_results_table_and_report():
    result = BenchmarkResult(
        mode="Policy Enabled",
        concurrency=10,
        total_requests=100,
        successful_requests=100,
        failed_requests=0,
        duration_sec=0.1,
        requests_per_sec=1000.0,
        avg_latency_ms=5.0,
        p50_ms=4.8,
        p95_ms=6.2,
        p99_ms=7.1,
    )
    table = format_results_table([result])
    assert "| Mode | Concurrency | Requests/sec" in table
    assert "Policy Enabled" in table
    assert "1000.0" in table

    report = generate_markdown_report([result])
    assert "# MiniSWG Benchmark Results" in report
    assert "Policy Enabled" in report


@pytest.mark.asyncio
async def test_run_suite_mini_run(tmp_path):
    output_file = tmp_path / "test_results.md"
    results = await run_suite(
        concurrencies=[5],
        total_requests=20,
        modes=["Policy Enabled", "Policy Disabled"],
        output_path=str(output_file),
    )

    assert len(results) == 2
    assert results[0].mode == "Policy Enabled"
    assert results[0].concurrency == 5
    assert results[0].successful_requests == 20
    assert results[0].failed_requests == 0

    assert results[1].mode == "Policy Disabled"
    assert results[1].concurrency == 5
    assert results[1].successful_requests == 20
    assert results[1].failed_requests == 0

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "# MiniSWG Benchmark Results" in content
    assert "Policy Enabled" in content
    assert "Policy Disabled" in content
