"""Benchmark key API reads against local or Neon-backed app configuration."""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from pathlib import Path
from typing import Iterable

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped or stripped.startswith("NEXT_PUBLIC_"):
            continue
        key, value = stripped.split("=", 1)
        values[key] = value
    return values


def merged_env(paths: Iterable[Path]) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in paths:
        values.update(load_env_file(path))
    return values


def select_env(target: str) -> dict[str, str]:
    root_env = REPO_ROOT / ".env"
    local_env = REPO_ROOT / ".env.local"
    if target == "local":
        return merged_env([root_env, local_env])
    if target == "neon":
        return merged_env([root_env])
    raise ValueError(f"Unsupported target: {target}")


def benchmark_paths() -> list[tuple[str, str]]:
    return [
        ("rankings_us", "/api/v1/rankings?market=US&asset_type=stock&limit=20"),
        ("rankings_kr", "/api/v1/rankings?market=KR&asset_type=stock&limit=20"),
        ("search_nv", "/api/v1/search?q=nv&limit=10"),
        ("search_sa", "/api/v1/search?q=%EC%82%BC&market=KR&limit=10"),
        ("strategy_canslim", "/api/v1/strategies/canslim/rankings?market=US&limit=20"),
        ("instrument_detail_nvda", "/api/v1/instruments/NVDA?market=US"),
        ("instrument_detail_005930", "/api/v1/instruments/005930?market=KR"),
        (
            "instrument_chart_nvda",
            "/api/v1/instruments/NVDA/chart?market=US&interval=1d&range_days=365&include_indicators=true",
        ),
        (
            "instrument_chart_005930",
            "/api/v1/instruments/005930/chart?market=KR&interval=1d&range_days=365&include_indicators=true",
        ),
        ("universe_coverage", "/api/v1/universe/coverage"),
    ]


async def run_benchmark(target: str, repeats: int, warmup: int) -> int:
    env = select_env(target)
    for key, value in env.items():
        os.environ[key] = value

    from app.main import app  # noqa: PLC0415

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://benchmark.local") as client:
        print(f"Target: {target}")
        print(f"Host: {env.get('POSTGRES_HOST')}")
        print(f"Pooler: {env.get('POSTGRES_HOST_POOLER') or '<none>'}")
        print()

        for name, path in benchmark_paths():
            samples: list[float] = []
            status_codes: list[int] = []
            last_error = ""
            for _ in range(warmup):
                try:
                    await client.get(path)
                except Exception:
                    break
            for _ in range(repeats):
                started = time.perf_counter()
                try:
                    response = await client.get(path)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    samples.append(elapsed_ms)
                    status_codes.append(response.status_code)
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    samples.append(elapsed_ms)
                    status_codes.append(-1)
                    last_error = f"{type(exc).__name__}: {exc}"

            mean_ms = statistics.mean(samples)
            p95_ms = max(samples) if len(samples) < 2 else statistics.quantiles(samples, n=20)[18]
            suffix = f" error={last_error}" if last_error else ""
            print(
                f"{name:24} status={status_codes[-1]} "
                f"mean_ms={mean_ms:8.2f} p95_ms={p95_ms:8.2f} "
                f"min_ms={min(samples):8.2f} max_ms={max(samples):8.2f}{suffix}"
            )

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=["local", "neon"], default="local")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()
    return asyncio.run(run_benchmark(args.target, args.repeats, args.warmup))


if __name__ == "__main__":
    raise SystemExit(main())
