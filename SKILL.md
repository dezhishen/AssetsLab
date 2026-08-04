---
name: webflow-cli
description: >-
  AssetsLab 工作流 CLI（python -m workflow / webflow-cli）命令行手册。
  调度骨架→测试→捕获→预览→导出流水线；参数化动作（stride/pelvis_bob/arm_swing）、
  风格模板（realistic/cartoon/bouncy/heavy/light）、体型比例（实例级 body）、
  制品导出（dist/<workflow_id>）与更新（GitHub Releases 三制品）。
  给 AI 代理的命令行调度指南：创建实例、运行/评审动作、调参、导出制品。
---

# webflow-cli — 命令行手册（SKILL）

纯命令行的工作流引擎。源码入口 `python -m workflow`，或打包二进制 `webflow-cli`，二者命令完全一致。Web/API 是另一通道（见 README），本 skill 只讲命令行操作。

## 安装

**方式 A：源码（推荐，含完整渲染工具链）**
```bash
git clone git@github.com:dezhishen/AssetsLab.git && cd AssetsLab
python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
# CLI 入口：.venv/bin/python -m workflow <verb>
```

**方式 B：二进制（免 Python）**
```bash
# 从 GitHub Releases 下载 webflow-cli-<linux|macos|windows>.zip 并解压
./webflow-cli <verb> ...        # Linux/macOS 若缺执行权限：chmod +x webflow-cli
```

**更新 CLI 与制品**：
```bash
python -m workflow update --component cli        # 更新 CLI 二进制
python -m workflow update --component frontend   # 更新前端 dist（供 server 用）
python -m workflow update --component server     # 更新 server 二进制
# 参数：--webflow-repo <owner/repo>（默认 git remote 推断）、--webflow-version <tag>、--webflow-token <PAT>
```

## 命令一览

| 命令 | 作用 |
|---|---|
| `list` | 列出实例（进度） |
| `new` | 新建实例（`--definition` / `--id` / `--template` / `--body-template` / `--body`） |
| `status` | 实例状态 + template + body + 各动作 params + 推荐 next |
| `next` | 推荐下一步动作 id |
| `run` | 运行动作（`--param` 动作参数 / `--body` 体型覆盖） |
| `approve` / `reject` | 评审（`--by` / `--note`） |
| `history` | 运行时间线 |
| `set-body` | 固化角色体型（实例级） |
| `update` | 更新制品（frontend / cli / server） |

所有命令支持 `--json`（机器可读输出）。

## 核心流程

```bash
# 1. 建实例（风格模板 + 体型模板）
python -m workflow new --definition default --id hero --template cartoon --body-template chibi --json

# 2. 查看状态与推荐下一步
python -m workflow status --workflow hero --json
python -m workflow next --workflow hero

# 3. 运行动作（可调动作参数 / 体型覆盖）
python -m workflow run --workflow hero --action skeleton.front --param stride=1.2 --param pelvis_bob=1.5
python -m workflow run --workflow hero --action skeleton.front --body head_scale=1.4

# 4. 评审
python -m workflow approve --workflow hero --action skeleton.front --by ai --note "ok"
python -m workflow reject --workflow hero --action skeleton.front --by ai --note "改大步幅"

# 5. 走完 7 步 → 导出制品（atlas + runtime_manifest.json + gif → dist/<workflow_id>/）
python -m workflow run --workflow hero --action export.artifacts
```

**动作 id（7 步精简版）**：`skeleton.front` → `skeleton.side` → `skeleton.back` → `test.smoke` → `capture.walk` → `preview.publish` → `export.artifacts`。定义在 `workflow/definitions/default.json`。

## 动作 / 体型分离

- **动作参数**（每动作，怎么动）：`stride` / `pelvis_bob` / `arm_swing`，用 `--param` 调。
- **体型比例**（角色，长什么样，实例级 `state.body`，三视图共享）：`arm_length` / `leg_length` / `torso_length` / `shoulder_width` / `head_scale` / `height`（1.0=基准），用 `--body` / `set-body` 调。两者正交。

**参数优先级**（动作参数）：运行时 `--param` > 实例模板 `template_params` > 定义默认值。
**体型优先级**（角色比例）：运行时 `--body` > 实例 `body`（`new --body-template`/`--body` 设定，`set-body` 修改）> 默认 1.0。

**风格参数模板**（`workflow/templates/*.json`）：`realistic`(1.0/0.7/0.8)、`cartoon`(1.7/1.6/1.5)、`bouncy`(1.3/2.0/1.2)、`heavy`(1.6/1.8/0.9)、`light`(0.8/1.1/1.3) —— 顺序对应 stride/pelvis_bob/arm_swing。

**体型模板**（`workflow/body/*.json`）：`standard`(标准成人)、`chibi`(大头Q版)、`tall`(高挑模特)、`stocky`(矮壮力量型)。体型=角色属性，实例级共享。

## 渲染执行（底层 assetslab CLI）

工作流的 `run` 会调用 `assetslab.py` 渲染；也可直接调底层命令：

```bash
# 动作预设（pose library：walk/run/idle/jump）
python workflow/tools/assetslab.py motion list
python workflow/tools/assetslab.py motion render run --view front --stage arms --ik --proportion-head-scale 1.4
python workflow/tools/assetslab.py motion check        # walk == 内置姿态逐像素一致

# 骨架阶段渲染（Pillow python 渲染器）
python workflow/tools/assetslab.py stage front arms --renderer python --motion walk --stride 1.2

# 启动预览服务器（REST API + Web 控制台，供人工通道）
python workflow/tools/lan_preview_server.py --port 8765 --directory prototype/preview
```

- **动作预设**：`workflow/motions/{walk,run,idle,jump}.json`，声明式（波形信号 + 关节偏移 + root + ik）。新动作 = 新 JSON，无需改渲染器。
- **一致性**：`motion check` 验证数据驱动 walk 与内置姿态逐像素一致（默认参数/比例）。
- **根驱动**：骨盆运动（bob/跳跃/前倾）经 `base.json` 的 `torso` 系数传导到肩/臂/头。
- **IK**：`--ik`（run/jump 预设声明）腿长恒定 + 脚落地锁定。

## 给 AI 的推荐执行路径

1. `new --template <风格> --body-template <体型>` 建实例 → `status` 确认 template_params + body
2. `next` 取推荐动作 → `run`（`--param` 调动作、`--body` 调体型；也可先 `set-body` 固化角色）
3. `status --json` 看该动作 `outputs`（本地图片绝对路径）+ `params`（实际所用动作+体型）
4. 满意 `approve`（带 note）→ 不满意 `reject`（附调整建议）→ 重新 `run`
5. 走完 7 步 → `export.artifacts` → 制品供 Godot demo

## 约定与注意事项

- 所有命令默认在**仓库根**执行；`--json` 输出机器可读，`outputs` 返回本地图片绝对路径。
- 状态按实例持久化 `run/workflows/<id>/state.json`（git 忽略）。
- 二进制（`webflow-cli`）的**管理/调度命令独立可用**；渲染类命令（run/stage）在目标机无 Python 时需用源码方式（二进制完整进程内化见 README）。
- 修改骨架基座/动作后跑 `motion check` 确认与内置姿态一致。
- 渲染默认 `--renderer python`（Pillow）；`godot` 渲染器仅一致性验证。
