# AssetsLab — 任务交接 / TODO

> 本文件用于项目内交接：新会话/伙伴接手时先读本文件 + `README_ZH.md` + `PROJECT.md`。
> 当前主线：**3D 动作系统（CMU 动捕数据驱动）+ 物种/预设 + CLI/HTTP 统一 Api + Godot demo**。

## 一、已完成（最近会话）

- **骨骼与 walk 按真实 CMU 动捕重建**（subject16, `16_15.bvh`）：骨长比例精确一致、全关节旋转照搬；`verify_motions3d.py` walk 8 项全 PASS。
- **统一 Api**：`interfaces.Api`（Protocol, @runtime_checkable）声明全部操作，`api.ApiService` 唯一实现（组合物种+预设+渲染），`make_api()` 运行时硬约束；CLI（`python -m assetslab.cli`）与 HTTP（server.py）共用同一套接口，避免两侧漂移。
- **预设系统**：`presets.py`（CRUD + schema 派生，值存 `data/presets/<id>.json`（数据目录默认仓库根 data/，--data-dir 可覆盖），schema 由物种派生不落盘）；前端独立入口（PresetsView：体型参数 + 动作幅度 + 实时预览）；CLI `preset new/create/list/...`。
- **dev 模式**：后端 `--dev`（CORS + OPTIONS）、前端 `pnpm run dev`（Vite 5173，proxy `/api` → 8765），前后端分离热更新；`pnpm approve-builds --all` 解决 esbuild 构建忽略问题。
- **3D 相机改造**：轨道相机（预览图拖拽旋转 + 快捷按钮 + 收纳面板），`useOrbitDrag`（isDragging 必须 ref）。
- **清理过时内容**：skins / packaging / build / webflow 发布链 / 旧参考资产；保留 `prototype/`（Godot demo）、`scripts/mocap/`、`verify_motions3d.py`。
- **前端动作预览**：`MotionPreview.vue` 封装播放 + 导出 GIF（后端 `gif=1`）。
- **全量测试**：E2E 10 用例全通过（物种/预设 CRUD、渲染、GIF、相机）；CLI 流程化测试 5 用例（`scripts/test_cli.py`，物种/动作/预设/渲染/错误处理，数据隔离 `test-data-cli/`）。
- **跨平台发布**：pyinstaller 构建嵌入 web 的 `assetslab-server`/`assetslab-cli` 二进制；GitHub Actions（`.github/workflows/release.yml`）矩阵产出 Linux/Windows/macOS，`v*` tag 触发（含 `-rc/-beta/-alpha` 预览版）；CHANGELOG 采用 Keep a Changelog + SemVer，Release Notes 按 tag 自动提取。

## 二、当前结构

| 路径 | 说明 |
|---|---|
| `assetslab/api.py / interfaces.py / cli.py / server.py` | 统一 Api（CLI+HTTP 共享）+ 薄路由 + CLI |
| `assetslab/species.py / presets.py / skeleton3d.py / motion.py` | 物种 / 预设 / 3D 引擎（FK/IK）/ DSL |
| `data/species/human/` | 骨骼 + default（CMU 体型）+ actions3d/walk3d |
| `data/presets/` | 预设（物种实例：body + actions；运行时用户数据） |
| `assetslab/web/` | Vue 3 前端（物种 / 预设独立入口） |
| `scripts/mocap/` | CMU 工具链（bvh_parser / rebuild_skeleton_cmu / extract_kin / compare_motion） |
| `scripts/verify_motions3d.py` | 3D 动作验证（8 项检查，数据驱动） |
| `scripts/test_cli.py` | CLI 流程化测试（unittest，物种/动作/预设/渲染，数据隔离 test-data-cli/） |
| `scripts/build_release.py` | pyinstaller 跨平台构建（server 嵌入 web + 物种数据，产物带版本号） |
| `.github/workflows/release.yml` | 跨平台发布（`v*` tag → 构建 + Release，预发布自动 Pre-release） |
| `CHANGELOG.md` | 变更日志（Keep a Changelog + SemVer：MAJOR/MINOR/PATCH + 预发布） |
| `prototype/` | **Godot 4.7 demo（保留）** |

## 三、下一步（待办）

1. **[P0] run / jump 同样用 CMU 真实数据**（`16_35.bvh` run、`16_01.bvh` jump），方法同 walk（`rebuild_skeleton_cmu.py` 扩展或新增生成）。
2. **[P1] 其他动作**（idle 等）按真实/合理数据补全，并给每个动作定义 `params`（动作幅度 schema）。
3. **[P2] Godot demo 接入 3D 动作**：确认 `prototype/` 消费 `dist/<id>/` 制品的流程（`scripts/build_demo.sh`）。
4. **[P2] Web 前端**：预设实时预览打磨、多动作切换、物种 default 编辑 UI。

## 四、关键命令

```bash
# 验证 3D 动作
.venv/bin/python scripts/verify_motions3d.py --species human --action walk3d

# CMU 真实骨骼/walk 重建（数据驱动，勿手工改 JSON）
.venv/bin/python scripts/mocap/rebuild_skeleton_cmu.py --inspect   # 查看 CMU 数据特征
.venv/bin/python scripts/mocap/rebuild_skeleton_cmu.py --skeleton  # 重建 default.json positions_3d
.venv/bin/python scripts/mocap/rebuild_skeleton_cmu.py --walk      # 重建 walk3d.json（真实旋转）

# CLI（与 HTTP 同级，同一套 Api，不启动 server）
.venv/bin/python -m assetslab.cli species list
.venv/bin/python -m assetslab.cli render skeleton human --out skel.png --yaw 45
.venv/bin/python -m assetslab.cli render motion walk3d --gif --out walk.gif

# 开发：后端 --dev + 前端 pnpm run dev（proxy /api → 8765）
.venv/bin/python assetslab/server.py --dev --port 8765
cd assetslab/web && pnpm run dev
```

## 五、已知坑 / 约定

1. **数据驱动**：骨骼/动作参数一律从真实 CMU BVH 提取，不要手工设计参数（用户明确要求）。
2. **统一 Api**：新增任何操作必须先声明到 `interfaces.Api`（CLI/HTTP 两侧自动一致）；`ApiService` 是实现。
3. **FK 语义**：位置用父累积旋转（不含自身）；FK 分支跳过 rigid_chains（避免覆盖真实脚位）。
4. **循环走**：root3d.z 移除（原地走，腿步幅真实），否则周期 wrap 会跳变。
5. **周期检测**：完整步态周期 = 同侧着地（间隔 2），自动选姿势差最小（walk 用 139 帧，差 11.4°）。
6. **elbow 检查**：用解剖学 shoulder-elbow-wrist 三点（walk 肘屈 18~35° 匹配真实）。
7. **dev 模式**：pnpm 11 的 esbuild 构建需 `pnpm approve-builds --all`；`useOrbitDrag.isDragging` 必须是 ref。
8. **环境**：用 `.venv/`（Pillow 12.3.0）；纯 Python（无 numpy/scipy）。
