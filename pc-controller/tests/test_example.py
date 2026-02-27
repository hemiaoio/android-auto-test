"""Example test cases demonstrating the AutoTest DSL."""

import asyncio

from autotest.automation.decorators import test_case
from autotest.automation.dsl import Device


@test_case(name="App Launch Test", tags=["smoke", "launch"])
async def test_app_launch(device: Device):
    """Verify that the target app launches successfully."""
    launch_time = await device.app("com.example.app").launch(clear_state=True)
    assert launch_time < 5000, f"Launch took too long: {launch_time}ms"

    # Verify main screen is displayed
    result = await device.ui(text_contains="Home").wait_for(timeout=10)
    assert result.found, "Home screen not displayed after launch"


@test_case(name="Login Flow Test", tags=["smoke", "login"])
async def test_login(device: Device):
    """End-to-end login flow test."""
    await device.app("com.example.app").launch(clear_state=True)

    # Input credentials
    await device.ui(resource_id="et_username").type("testuser")
    await device.ui(resource_id="et_password").type("password123")

    # Submit
    await device.ui(text="Login").click()

    # Verify success
    welcome = await device.ui(text_contains="Welcome").wait_for(timeout=15)
    assert welcome.found, "Login failed: welcome screen not found"

    # Take evidence screenshot
    await device.screenshot(tag="login_success")


@test_case(name="Performance Baseline", tags=["perf", "baseline"])
async def test_performance_baseline(device: Device):
    """Collect performance baseline metrics for 30 seconds."""
    perf = await device.perf.start(
        package="com.example.app",
        metrics=["cpu", "memory", "fps"],
        interval_ms=500,
    )

    await device.app("com.example.app").launch()
    await asyncio.sleep(30)

    report = await perf.stop()

    # Assert performance thresholds
    assert report.avg_cpu < 40, f"CPU too high: {report.avg_cpu}%"
    assert report.avg_fps > 50, f"FPS too low: {report.avg_fps}"
    assert report.avg_memory < 300, f"Memory too high: {report.avg_memory}MB"
    assert report.jank_count < 10, f"Too many janks: {report.jank_count}"


@test_case(name="Navigation Test", tags=["regression", "navigation"])
async def test_navigation(device: Device):
    """Test basic navigation between screens."""
    await device.app("com.example.app").launch()

    # Navigate to settings
    await device.ui(content_description="Settings").click()
    result = await device.ui(text="Settings").wait_for(timeout=5)
    assert result.found, "Settings screen not displayed"

    # Go back
    await device.press_back()
    result = await device.ui(text_contains="Home").wait_for(timeout=5)
    assert result.found, "Failed to navigate back to home"
