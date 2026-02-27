"""CLI interface for the AutoTest framework."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from autotest.core.config import load_dotenv

# CLI 启动时自动加载 .env 文件
load_dotenv()

app = typer.Typer(name="autotest", help="Industrial-grade Android App automation platform")
console = Console()


@app.command()
def devices() -> None:
    """List all connected devices."""

    async def _list() -> None:
        from autotest.device.adb import AdbClient

        adb = AdbClient()
        devs = await adb.devices()

        table = Table(title="Connected Devices")
        table.add_column("Serial", style="cyan")
        table.add_column("State", style="green")
        table.add_column("Model")

        for d in devs:
            state_style = "green" if d.state == "device" else "red"
            table.add_row(d.serial, f"[{state_style}]{d.state}[/]", d.model)

        console.print(table)

    asyncio.run(_list())


@app.command()
def run(
    paths: list[str] = typer.Argument(..., help="Test file or directory paths"),
    tags: list[str] = typer.Option([], "--tags", "-t", help="Filter by tags"),
    device: str | None = typer.Option(None, "--device", "-d", help="Target device serial"),
    parallel: bool = typer.Option(False, "--parallel", "-p", help="Run on all devices in parallel"),
    output: str = typer.Option("./reports", "--output", "-o", help="Report output directory"),
    formats: list[str] = typer.Option(["html"], "--formats", "-f", help="Report formats"),
) -> None:
    """Run test cases."""

    async def _run() -> None:
        from autotest.automation.runner import TestRunner
        from autotest.core.events import EventBus
        from autotest.device.manager import DeviceManager

        event_bus = EventBus()
        runner = TestRunner(event_bus)

        # Discover tests
        tests = runner.discover(paths)
        if tags:
            tests = runner.filter_tests(tests, tags=tags)

        if not tests:
            console.print("[yellow]No tests found[/yellow]")
            return

        console.print(f"Found [cyan]{len(tests)}[/cyan] test(s)")

        # Connect to devices
        async with DeviceManager() as manager:
            if device:
                client = await manager.connect(device)
                clients = [client]
            else:
                clients = await manager.connect_all()

            if not clients:
                console.print("[red]No devices available[/red]")
                return

            console.print(f"Connected to [cyan]{len(clients)}[/cyan] device(s)")

            # Run tests
            if parallel and len(clients) > 1:
                from autotest.scheduler.executor import ParallelExecutor
                executor = ParallelExecutor(manager, event_bus)
                exec_result = await executor.execute(tests, strategy="round_robin")
                all_results = exec_result.results
            else:
                all_results = []
                for client in clients:
                    results = await runner.run(tests, client)
                    all_results.extend(results)

            # Print summary
            table = Table(title="Test Results")
            table.add_column("Test", style="cyan")
            table.add_column("Device")
            table.add_column("Status")
            table.add_column("Duration")
            table.add_column("Error", max_width=50)

            for r in all_results:
                status_style = {
                    "passed": "green",
                    "failed": "red",
                    "error": "red bold",
                    "skipped": "yellow",
                }.get(r.status.value, "white")

                table.add_row(
                    r.name,
                    r.device_serial,
                    f"[{status_style}]{r.status.value.upper()}[/]",
                    f"{r.duration_ms:.0f}ms",
                    r.error_message or "-",
                )

            console.print(table)

            passed_count = sum(1 for r in all_results if r.status.value == "passed")
            total_count = len(all_results)
            console.print(f"\n[bold]{passed_count}/{total_count} passed[/bold]")

            # Generate reports
            if all_results:
                from autotest.reporter.generator import ReportGenerator
                generator = ReportGenerator(output)
                generated = generator.generate(all_results, formats=formats)
                for path in generated:
                    console.print(f"Report: [blue]{path}[/blue]")

    asyncio.run(_run())


@app.command()
def info(serial: str = typer.Argument(..., help="Device serial number")) -> None:
    """Get detailed device information."""

    async def _info() -> None:
        from autotest.device.manager import DeviceManager

        async with DeviceManager() as manager:
            client = await manager.connect(serial)
            from autotest.automation.dsl import Device
            device = Device(client)
            dev_info = await device.info()

            console.print(f"[bold]Device Info: {serial}[/bold]")
            console.print(f"  Model: {dev_info.model}")
            console.print(f"  Manufacturer: {dev_info.manufacturer}")
            console.print(f"  Android: {dev_info.android_version} (SDK {dev_info.sdk_version})")
            console.print(f"  Screen: {dev_info.screen_width}x{dev_info.screen_height}")
            console.print(f"  Root: {'Yes' if dev_info.is_rooted else 'No'}")
            console.print(f"  Accessibility: {'Enabled' if dev_info.is_accessibility_enabled else 'Disabled'}")

    asyncio.run(_info())


@app.command()
def report(
    input_dir: str = typer.Argument("./reports", help="Report input directory"),
    formats: list[str] = typer.Option(["html"], "--formats", "-f", help="Report formats to generate"),
) -> None:
    """Generate reports from saved test results."""
    from pathlib import Path
    import json

    json_path = Path(input_dir) / "report.json"
    if not json_path.exists():
        console.print("[red]No report.json found in input directory[/red]")
        return

    data = json.loads(json_path.read_text())
    from autotest.core.types import TestResult, TestStatus
    results = [
        TestResult(
            name=r["name"],
            status=TestStatus(r["status"]),
            duration_ms=r.get("duration_ms", 0),
            device_serial=r.get("device", ""),
            error_message=r.get("error"),
        )
        for r in data.get("results", [])
    ]

    from autotest.reporter.generator import ReportGenerator
    generator = ReportGenerator(input_dir)
    generated = generator.generate(results, formats=formats, perf_data=data.get("performance"))
    for path in generated:
        console.print(f"Generated: [blue]{path}[/blue]")


@app.command()
def dashboard(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Dashboard host"),
    port: int = typer.Option(8080, "--port", "-p", help="Dashboard port"),
    report_dir: str = typer.Option("./reports", "--reports", "-r", help="Reports directory"),
) -> None:
    """Start the web dashboard for real-time monitoring."""
    console.print(f"Starting dashboard at [blue]http://{host}:{port}[/blue]")
    from autotest.web.app import run_dashboard
    run_dashboard(host=host, port=port, report_dir=report_dir)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
