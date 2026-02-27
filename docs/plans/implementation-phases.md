# AutoTest 实施阶段计划

## 概览

项目分为 6 个阶段，从基础骨架到平台化部署，逐步构建完整的自动化测试平台。

---

## Phase 1: 基础骨架（设备端核心）

### 目标
搭建 Android Gradle 多模块项目，实现基本的通信链路。

### 任务
1. 创建 Gradle 多模块 Android 项目结构（7 个模块）
2. 实现 `agent-protocol` 消息定义（Message, Methods, ErrorCodes, Events）
3. 实现 `agent-transport` WebSocket 服务端（Ktor 三端口）
4. 实现 `agent-core` 引擎骨架（AgentEngine + CommandRouter + CapabilityResolver）
5. 实现 `agent-app` 前台 Service + 基础 UI

### 验证标准
- Agent App 安装到设备后启动成功
- PC 端通过 WebSocket 连接，发送 `device.info` 收到正确响应

### 状态: 已完成

---

## Phase 2: 双模式自动化引擎

### 目标
实现 Root 和非 Root 两种模式的 UI 自动化操作。

### 任务
6. 实现 `agent-accessibility` AccessibilityService + UI 操作
7. 实现 `agent-root` Root 检测 + Shell 执行器 + Root 操作
8. 实现 `CapabilityResolver` 策略自动切换
9. 实现控件查找/点击/输入/滑动/截图的完整链路

### 验证标准
- 通过 ADB 连接设备
- 执行 `ui.click` / `ui.type` 操作目标 App
- Root 和非 Root 模式均可工作

### 状态: 已完成

---

## Phase 3: PC 端控制器

### 目标
构建 Python PC 端，实现完整的测试编写和执行流程。

### 任务
10. 创建 Python 项目结构（pyproject.toml）
11. 实现 `device/adb.py` ADB 封装
12. 实现 `device/client.py` WebSocket 客户端
13. 实现 `device/manager.py` 多设备管理
14. 实现 `automation/dsl.py` 流式 API（Device / UiSelector / AppController）
15. 实现 `automation/runner.py` 测试执行引擎

### 验证标准
- 用 Python DSL 编写一个简单登录测试用例
- 在真机上端到端执行通过

### 状态: 已完成

---

## Phase 4: 性能采集 & 高级功能

### 目标
实现设备端性能指标采集和 PC 端数据分析、报告生成。

### 任务
16. 实现 `agent-performance` 各项指标采集器
    - CPU 采集器（/proc/stat 解析）
    - 内存采集器（dumpsys meminfo）
    - FPS 采集器（SurfaceFlinger / gfxinfo）
    - 网络采集器（/proc/net/dev）
    - 电量采集器（/sys/class/power_supply）
17. 实现 PC 端 `performance/analyzer.py` 数据分析（P50/P90/P99 统计）
18. 实现 `reporter/` 测试报告生成
    - HTML 报告（含 SVG 图表）
    - JSON 报告
    - JUnit XML 报告
    - Allure 报告
19. 实现 `cli/app.py` 命令行工具

### 验证标准
- 运行性能采集 30 秒
- 生成包含 CPU/内存/FPS 曲线的 HTML 报告

### 状态: 已完成

---

## Phase 5: 插件体系 & 扩展

### 目标
实现双端插件系统，开发内置插件。

### 任务
20. 实现设备端 PluginManager（DexClassLoader 动态加载）
21. 实现 PC 端 PluginHost（entry_points + 目录扫描）
22. 开发内置插件
    - OCR 文字识别
    - 图像模板匹配
    - 视觉回归对比
23. 实现录制回放功能（预留）

### 验证标准
- 加载 OCR 插件
- 用图像识别方式定位一个控件并点击

### 状态: 已完成

---

## Phase 6: 平台化 & CI/CD

### 目标
实现多设备并行调度、Web Dashboard 和 CI/CD 集成。

### 任务
24. 实现 `scheduler/` 多设备并行调度
    - TestPlanner 分配策略（round_robin / capability_match / duplicate）
    - ParallelExecutor 并行执行器
25. 实现 `web/` FastAPI Dashboard
    - 实时 WebSocket 事件推送
    - 报告浏览
    - 设备状态监控
26. 编写 CI/CD 集成模板（GitHub Actions / Jenkins）
27. 编写使用文档和示例

### 验证标准
- 3 台设备并行执行测试套件
- Web Dashboard 实时展示进度和结果

### 状态: 已完成

---

## 代码统计

| 分类 | 文件数 | 行数（约） |
|------|--------|-----------|
| Kotlin (设备端) | 34 | ~3,000 |
| Python (PC 端) | 43 | ~3,400 |
| **总计** | **77** | **~6,400** |

---

## 推荐的后续增强

| 能力 | 说明 | 优先级 |
|------|------|--------|
| AI 控件识别 | 当 A11y 树失效时，用图像匹配+OCR 兜底定位 | P1 |
| 智能等待策略 | 基于 UI 状态变化+idle 检测的等待 | P1 |
| 录制回放 | 录制用户操作自动生成 Python 测试脚本 | P1 |
| Crash 自动归因 | 捕获 Crash 堆栈+截图+操作回放日志 | P2 |
| 网络抓包 | VPN 模式(非Root) / tcpdump(Root) | P2 |
| Monkey 增强 | 基于控件树的智能随机测试 | P2 |
| 电量画像 | 长时间采集电量消耗曲线 | P3 |
| 无障碍合规检测 | 自动扫描 App 的无障碍问题 | P3 |
