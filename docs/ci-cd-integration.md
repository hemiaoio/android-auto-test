# AutoTest CI/CD 集成指南

## 1. GitHub Actions

### 1.1 基本工作流

```yaml
# .github/workflows/android-test.yml
name: Android Automation Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点

jobs:
  test:
    runs-on: [self-hosted, android-device]  # 需要自托管 Runner 连接真机

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          cd pc-controller
          pip install -e ".[web,report]"

      - name: Check devices
        run: |
          adb devices
          autotest devices

      - name: Build and install Agent
        run: |
          ./gradlew :agent-app:assembleDebug
          adb install -r agent-app/build/outputs/apk/debug/agent-app-debug.apk

      - name: Run smoke tests
        run: |
          autotest run tests/ --tags smoke --output ./reports --formats html --formats junit

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-reports
          path: reports/

      - name: Publish JUnit results
        if: always()
        uses: mikepenz/action-junit-report@v4
        with:
          report_paths: reports/report-junit.xml
```

### 1.2 多设备并行工作流

```yaml
# .github/workflows/parallel-test.yml
name: Parallel Device Tests

on:
  workflow_dispatch:
    inputs:
      tags:
        description: 'Test tags to run'
        default: 'smoke'
      strategy:
        description: 'Distribution strategy'
        default: 'round_robin'
        type: choice
        options:
          - round_robin
          - duplicate
          - single_device

jobs:
  test:
    runs-on: [self-hosted, device-farm]

    steps:
      - uses: actions/checkout@v4

      - name: Setup
        run: |
          cd pc-controller && pip install -e ".[report]"

      - name: Run parallel tests
        run: |
          autotest run tests/ \
            --tags ${{ github.event.inputs.tags }} \
            --parallel \
            --output ./reports \
            --formats html --formats junit --formats json

      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: parallel-reports-${{ github.run_number }}
          path: reports/
```

---

## 2. Jenkins Pipeline

### 2.1 Jenkinsfile

```groovy
pipeline {
    agent { label 'android-device' }

    parameters {
        string(name: 'TAGS', defaultValue: 'smoke', description: 'Test tags')
        booleanParam(name: 'PARALLEL', defaultValue: false, description: 'Run in parallel')
        choice(name: 'REPORT_FORMAT', choices: ['html', 'allure', 'junit'], description: 'Report format')
    }

    environment {
        PYTHON = 'python3'
        REPORTS_DIR = "${WORKSPACE}/reports"
    }

    stages {
        stage('Setup') {
            steps {
                sh '''
                    cd pc-controller
                    ${PYTHON} -m pip install -e ".[report]"
                '''
            }
        }

        stage('Check Devices') {
            steps {
                sh 'adb devices'
                sh 'autotest devices'
            }
        }

        stage('Install Agent') {
            steps {
                sh '''
                    ./gradlew :agent-app:assembleDebug
                    adb install -r agent-app/build/outputs/apk/debug/agent-app-debug.apk
                '''
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    def parallelFlag = params.PARALLEL ? '--parallel' : ''
                    sh """
                        autotest run tests/ \
                            --tags ${params.TAGS} \
                            ${parallelFlag} \
                            --output ${REPORTS_DIR} \
                            --formats ${params.REPORT_FORMAT} \
                            --formats junit
                    """
                }
            }
        }
    }

    post {
        always {
            junit 'reports/report-junit.xml'

            archiveArtifacts artifacts: 'reports/**', fingerprint: true

            script {
                if (params.REPORT_FORMAT == 'allure') {
                    allure includeProperties: false,
                           jdk: '',
                           results: [[path: 'reports/allure-results']]
                }
            }
        }

        failure {
            // 发送通知
            emailext (
                subject: "AutoTest Failed: ${env.JOB_NAME} #${env.BUILD_NUMBER}",
                body: "Check reports at: ${env.BUILD_URL}artifact/reports/",
                to: 'team@example.com'
            )
        }
    }
}
```

---

## 3. GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - report

variables:
  REPORTS_DIR: "./reports"

build-agent:
  stage: build
  tags: [android]
  script:
    - ./gradlew :agent-app:assembleDebug
  artifacts:
    paths:
      - agent-app/build/outputs/apk/debug/

install-and-test:
  stage: test
  tags: [android-device]
  dependencies:
    - build-agent
  script:
    - cd pc-controller && pip install -e ".[report]"
    - adb install -r agent-app/build/outputs/apk/debug/agent-app-debug.apk
    - autotest run tests/ --tags smoke --output $REPORTS_DIR --formats html --formats junit
  artifacts:
    when: always
    paths:
      - reports/
    reports:
      junit: reports/report-junit.xml

pages:
  stage: report
  dependencies:
    - install-and-test
  script:
    - mkdir -p public
    - cp -r reports/* public/
  artifacts:
    paths:
      - public
  only:
    - main
```

---

## 4. 编程式集成

### 4.1 Python 脚本集成

```python
"""ci_runner.py — 在 CI 环境中运行测试"""
import asyncio
import sys

from autotest.automation.runner import TestRunner
from autotest.core.events import EventBus
from autotest.device.manager import DeviceManager
from autotest.reporter.generator import ReportGenerator


async def main():
    event_bus = EventBus()
    runner = TestRunner(event_bus)

    # 发现并过滤测试
    tests = runner.discover(["tests/"])
    tests = runner.filter_tests(tests, tags=["smoke"])

    if not tests:
        print("No tests found")
        sys.exit(0)

    # 连接设备
    async with DeviceManager() as manager:
        clients = await manager.connect_all()
        if not clients:
            print("ERROR: No devices connected")
            sys.exit(1)

        # 执行测试
        all_results = []
        for client in clients:
            results = await runner.run(tests, client)
            all_results.extend(results)

    # 生成报告
    generator = ReportGenerator("./reports")
    generator.generate(all_results, formats=["html", "junit", "json"])

    # 根据结果设置退出码
    failed = sum(1 for r in all_results if r.status.value in ("failed", "error"))
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 并行执行集成

```python
"""ci_parallel_runner.py — 多设备并行执行"""
import asyncio
import sys

from autotest.automation.runner import TestRunner
from autotest.core.events import EventBus
from autotest.device.manager import DeviceManager
from autotest.scheduler.executor import ParallelExecutor
from autotest.reporter.generator import ReportGenerator


async def main():
    event_bus = EventBus()
    runner = TestRunner(event_bus)

    tests = runner.discover(["tests/"])

    async with DeviceManager() as manager:
        executor = ParallelExecutor(manager, event_bus, max_workers=8)
        result = await executor.execute(tests, strategy="round_robin")

    # 报告
    generator = ReportGenerator("./reports")
    generator.generate(result.results, formats=["html", "junit"])

    print(f"Results: {result.passed}/{result.total} passed ({result.pass_rate:.1f}%)")
    sys.exit(0 if result.is_success else 1)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 5. 环境配置建议

### 5.1 自托管 Runner 要求

| 要求 | 说明 |
|------|------|
| ADB | 已安装并加入 PATH |
| Python 3.10+ | 预装好 autotest 依赖 |
| USB Hub | 连接多台 Android 设备 |
| Agent APK | 预装到设备或在 CI 中安装 |
| 无障碍权限 | 如不用 Root 模式，需手动开启一次 |

### 5.2 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `AUTOTEST_ADB_PATH` | ADB 可执行文件路径 | `adb` |
| `AUTOTEST_CONFIG` | 配置文件路径 | `configs/default.yaml` |
| `AUTOTEST_REPORT_DIR` | 报告输出目录 | `./reports` |

---

## 6. 故障排查

### 设备无法连接

```bash
# 检查 ADB 连接
adb devices

# 重启 ADB 服务
adb kill-server && adb start-server

# 检查 Agent 是否运行
adb shell ps | grep auto.agent
```

### Agent 服务未启动

```bash
# 通过 ADB 启动 Agent Service
adb shell am startservice com.auto.agent.app/.AgentForegroundService
```

### 端口冲突

```bash
# 检查端口占用
adb forward --list
netstat -tlnp | grep 28900

# 清除端口转发
adb forward --remove-all
```
