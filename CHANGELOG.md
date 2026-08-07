# Changelog

本项目遵循 **Keep a Changelog**（[1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)）
与 **Semantic Versioning**（[2.0.0](https://semver.org/lang/zh-CN/)）。

版本格式：`主版本号.次版本号.修订号`（`MAJOR.MINOR.PATCH`）

- **主版本号（MAJOR）**：不兼容的 API 变更
- **次版本号（MINOR）**：向后兼容的功能新增（小版本）
- **修订号（PATCH）**：向后兼容的缺陷修复（fix 版本）
- **预发布**：`-alpha.N` / `-beta.N` / `-rc.N` 后缀，用于正式发布前的预览版

变更日志**有取舍**：每个版本只汇总用户可见的重要变更（按 Added / Changed / Fixed / Removed 分类），
不逐条罗列提交记录。

## [Unreleased]

## [0.3.0] - 2026-08-07

### Added
- **跨平台二进制发布**：pyinstaller 构建 `assetslab-server`（嵌入 Vue 前端）与 `assetslab-cli`，
  GitHub Actions 矩阵产出 Linux / Windows / macOS 二进制；`v*` tag 触发 GitHub Release（含预发布版）
- **CLI 流程化测试**：`scripts/test_cli.py`（unittest，物种/动作/预设/渲染全生命周期，数据隔离）
- **前端 E2E 全量测试**：10 个用例覆盖物种/预设 CRUD、渲染、GIF 导出、轨道相机

### Changed
- **数据目录可配置**：`--data-dir`（默认仓库根 `data/`），测试用独立的 `test-data/`；
  打包运行时物种数据从 bundle 首次播种到用户可写目录
- **数据定义精简**：`skeleton.json` 采用纯 3D 定义（`bones_3d` / `fk_tree`），无历史视图数据

### Fixed
- 前端 E2E：el-select 下拉弹层在 720 视口下超界导致的点击失败（改 DOM click）

## [0.2.0] - 2026-06-20

### Added
- **预设系统**：`presets.py`（CRUD + schema 派生），前端独立入口（体型参数 + 动作幅度 + 实时预览）
- **统一 Api**：`interfaces.Api`（Protocol）声明全部操作，`api.ApiService` 唯一实现，CLI 与 HTTP 共享
- **3D 轨道相机**：预览图拖拽旋转 + 快捷视角按钮 + 收纳面板（`CameraControls` / `useOrbitDrag`）
- **动作预览与 GIF 导出**：`MotionPreview.vue` 播放 + 导出 GIF（后端 `gif=1`）
- **dev 模式**：后端 `--dev`（CORS）+ 前端 Vite dev（proxy `/api`），前后端分离热更新

### Changed
- 清理过时内容：skins / packaging / webflow 发布链（保留 Godot demo `prototype/`）

## [0.1.0] - 2026-05-25

### Added
- **3D 骨架引擎**：`skeleton3d.py`（FK 正向运动学 + 3D IK + 透视投影 `project3d`），任意视角渲染 PNG/GIF
- **真实 CMU 动捕数据**：subject16 `16_15.bvh` 重建骨骼与 walk 动作（骨长比例精确一致、全关节旋转照搬）
- **动作验证**：`verify_motions3d.py`（8 项检查：骨长/贴地/平滑/对称/关节/肘/坐标/参数，数据驱动）
- **HTTP API**：`server.py`（物种 CRUD + 3D 骨架/动作渲染端点）
- **CLI**：`assetslab.cli`（物种/动作管理 + 渲染命令）
- **Vue 前端**：物种管理（列表/详情/骨架预览/动作编辑器）
