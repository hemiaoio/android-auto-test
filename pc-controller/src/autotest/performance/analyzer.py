"""Performance data analysis and statistics."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerfAnalysisResult:
    duration_ms: float = 0
    sample_count: int = 0
    cpu: CpuAnalysis | None = None
    memory: MemoryAnalysis | None = None
    fps: FpsAnalysis | None = None
    network: NetworkAnalysis | None = None
    battery: BatteryAnalysis | None = None


@dataclass
class CpuAnalysis:
    avg: float = 0
    max: float = 0
    min: float = 0
    p50: float = 0
    p90: float = 0
    p99: float = 0
    samples: list[float] = field(default_factory=list)


@dataclass
class MemoryAnalysis:
    avg_pss_kb: float = 0
    max_pss_kb: float = 0
    min_pss_kb: float = 0
    leak_trend_kb_per_min: float = 0
    samples: list[float] = field(default_factory=list)


@dataclass
class FpsAnalysis:
    avg: float = 0
    min: float = 0
    p10: float = 0
    jank_count: int = 0
    big_jank_count: int = 0
    jank_rate: float = 0
    samples: list[float] = field(default_factory=list)


@dataclass
class NetworkAnalysis:
    total_rx_bytes: int = 0
    total_tx_bytes: int = 0
    avg_rx_speed: float = 0
    avg_tx_speed: float = 0
    peak_rx_speed: float = 0
    peak_tx_speed: float = 0


@dataclass
class BatteryAnalysis:
    start_level: int = 0
    end_level: int = 0
    drain_rate_per_hour: float = 0
    avg_temperature: float = 0
    max_temperature: float = 0


class PerfAnalyzer:
    """Analyzes raw performance data points from the device agent."""

    def analyze(self, data: dict[str, Any]) -> PerfAnalysisResult:
        points = data.get("dataPoints", [])
        summary = data.get("summary", {})

        result = PerfAnalysisResult(
            duration_ms=data.get("durationMs", 0),
            sample_count=len(points),
        )

        cpu_samples = [p["cpu"]["app"] for p in points if "cpu" in p]
        if cpu_samples:
            result.cpu = self._analyze_cpu(cpu_samples)

        mem_samples = [p["memory"]["totalPss"] for p in points if "memory" in p]
        if mem_samples:
            result.memory = self._analyze_memory(mem_samples, result.duration_ms)

        fps_samples = [p["fps"]["current"] for p in points if "fps" in p]
        jank_samples = [p["fps"].get("jank", 0) for p in points if "fps" in p]
        if fps_samples:
            result.fps = self._analyze_fps(fps_samples, jank_samples)

        net_points = [p["network"] for p in points if "network" in p]
        if net_points:
            result.network = self._analyze_network(net_points)

        bat_points = [p["battery"] for p in points if "battery" in p]
        if bat_points:
            result.battery = self._analyze_battery(bat_points, result.duration_ms)

        return result

    def _analyze_cpu(self, samples: list[float]) -> CpuAnalysis:
        sorted_s = sorted(samples)
        return CpuAnalysis(
            avg=statistics.mean(samples),
            max=max(samples),
            min=min(samples),
            p50=self._percentile(sorted_s, 50),
            p90=self._percentile(sorted_s, 90),
            p99=self._percentile(sorted_s, 99),
            samples=samples,
        )

    def _analyze_memory(self, samples: list[float], duration_ms: float) -> MemoryAnalysis:
        trend = 0.0
        if len(samples) > 10 and duration_ms > 0:
            # Linear regression for leak detection
            first_quarter = statistics.mean(samples[: len(samples) // 4])
            last_quarter = statistics.mean(samples[3 * len(samples) // 4 :])
            minutes = duration_ms / 60_000
            if minutes > 0:
                trend = (last_quarter - first_quarter) / minutes

        return MemoryAnalysis(
            avg_pss_kb=statistics.mean(samples),
            max_pss_kb=max(samples),
            min_pss_kb=min(samples),
            leak_trend_kb_per_min=trend,
            samples=samples,
        )

    def _analyze_fps(self, fps_samples: list[float], jank_samples: list[int]) -> FpsAnalysis:
        sorted_fps = sorted(fps_samples)
        total_janks = sum(jank_samples)
        total_frames = len(fps_samples)

        return FpsAnalysis(
            avg=statistics.mean(fps_samples),
            min=min(fps_samples),
            p10=self._percentile(sorted_fps, 10),
            jank_count=total_janks,
            big_jank_count=0,
            jank_rate=(total_janks / total_frames * 100) if total_frames > 0 else 0,
            samples=fps_samples,
        )

    def _analyze_network(self, points: list[dict[str, Any]]) -> NetworkAnalysis:
        rx_speeds = [p.get("rxSpeed", 0) for p in points]
        tx_speeds = [p.get("txSpeed", 0) for p in points]

        return NetworkAnalysis(
            total_rx_bytes=points[-1].get("rxBytes", 0) - points[0].get("rxBytes", 0) if points else 0,
            total_tx_bytes=points[-1].get("txBytes", 0) - points[0].get("txBytes", 0) if points else 0,
            avg_rx_speed=statistics.mean(rx_speeds) if rx_speeds else 0,
            avg_tx_speed=statistics.mean(tx_speeds) if tx_speeds else 0,
            peak_rx_speed=max(rx_speeds) if rx_speeds else 0,
            peak_tx_speed=max(tx_speeds) if tx_speeds else 0,
        )

    def _analyze_battery(self, points: list[dict[str, Any]], duration_ms: float) -> BatteryAnalysis:
        levels = [p.get("level", 0) for p in points]
        temps = [p.get("temperature", 0) for p in points]

        hours = duration_ms / 3_600_000
        drain = levels[0] - levels[-1] if levels else 0
        drain_rate = drain / hours if hours > 0 else 0

        return BatteryAnalysis(
            start_level=levels[0] if levels else 0,
            end_level=levels[-1] if levels else 0,
            drain_rate_per_hour=drain_rate,
            avg_temperature=statistics.mean(temps) if temps else 0,
            max_temperature=max(temps) if temps else 0,
        )

    @staticmethod
    def _percentile(sorted_data: list[float], p: int) -> float:
        if not sorted_data:
            return 0
        k = (len(sorted_data) - 1) * p / 100
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)
