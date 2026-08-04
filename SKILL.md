---
name: webflow-cli
description: >-
  AssetsLab 工作流 CLI（webflow-cli）命令行手册。
  调度骨架→测试→捕获→预览→导出流水线；参数化动作（stride/pelvis_bob/arm_swing）、
  风格模板（realistic/cartoon/bouncy/heavy/light）、体型比例（实例级 body）、
  制品导出（dist/<workflow_id>）与更新（GitHub Releases 三制品）。
  给 AI 代理的命令行调度指南：创建实例、运行动作、调参、导出制品。
---

# webflow-cli — 命令行手册（SKILL）

纯命令行的 AssetsLab 工作流引擎，基于 GitHub Releases 发布的 `webflow-cli` 二进制（curl 一键安装）。Web/API 是另一通道（见 README），本 skill 只讲命令行操作。

## 安装（curl 二进制）

从 GitHub Releases 用 `curl` 下载 `webflow-cli` 二进制安装（无需 Python）。

**Linux / macOS**：
```bash
mkdir -p ~/.local/bin && cd ~/.local/bin
OS=linux; [ "$(uname)" = "Darwin" ] && OS=macos
TAG=latest                                        # 或指定版本，如 v1.0.0
BASE="releases/latest/download"; [ "$TAG" != "latest" ] && BASE="releases/download/$TAG"
curl -L -o webflow-cli.zip "https://github.com/dezhishen/AssetsLab/$BASE/webflow-cli-$OS.zip"
unzip -o webflow-cli.zip && chmod +x webflow-cli/webflow-cli
ln -sf "$PWD/webflow-cli/webflow-cli" ~/.local/bin/webflow-cli
export PATH="$HOME/.local/bin:$PATH"
webflow-cli --help
```

**Windows（PowerShell）**：
```powershell
curl.exe -L -o webflow-cli.zip https://github.com/dezhishen/AssetsLab/releases/latest/download/webflow-cli-windows.zip
tar -xf webflow-cli.zip
.\webflow-cli\webflow-cli.exe --help
```

**更新 CLI（自身）**：
```bash
webflow-cli update        # 更新 webflow-cli 二进制自身
# 参数：--webflow-repo <owner/repo>（非仓库目录运行需显式）、--webflow-version <tag>、--webflow-token <PAT>
```
> webflow-cli 只管理自己：**前端 dist** 由 server 启动时自动下载；**server 二进制**更新 = 重新 curl 安装新版 `webflow-server-<platform>.zip`。

## 命令一览

| 命令 | 作用 |
|---|---|
| `list` | 列出实例（进度） |
| `new` | 新建实例（`--definition` / `--id` / `--template` / `--body-template` / `--body`） |
| `status` | 实例状态 + template + body + 各动作 params + 推荐 next |
| `next` | 推荐下一步动作 id |
| `run` | 运行动作（`--param` 动作参数 / `--body` 体型覆盖；运行通过即自动进入下一步） |
| `history` | 运行时间线 |
| `set-body` | 固化角色体型（实例级） |
| `delete` | 删除实例（默认保留制品；`--remove-artifacts` 连同 `dist/<id>/` 一起删除） |
| `delete-artifacts` | 仅删除实例的导出制品（`dist/<id>/`），实例本身保留 |
| `update` | 更新 CLI 自身二进制 |

所有命令支持 `--json`（机器可读输出）。

## 核心流程

```bash
# 1. 建实例（风格模板 + 体型模板）
webflow-cli new --definition default --id hero --template cartoon --body-template chibi --json

# 2. 查看状态与推荐下一步
webflow-cli status --workflow hero --json
webflow-cli next --workflow hero

# 3. 运行动作（可调动作参数 / 体型覆盖；运行通过即自动进入下一步，无评审）
webflow-cli run --workflow hero --action skeleton.front --param stride=1.2 --param pelvis_bob=1.5
webflow-cli run --workflow hero --action skeleton.front --body head_scale=1.4

# 4. 走完 7 步 → 导出制品（atlas + runtime_manifest.json + gif → dist/<workflow_id>/）
webflow-cli run --workflow hero --action export.artifacts
```

**动作 id（6 步精简版）**：`skeleton.front` → `skeleton.side` → `skeleton.back` → `test.smoke` → `capture.walk` → `export.artifacts`。定义在 `workflow/definitions/default.json`。

## 动作 / 体型分离

- **动作参数**（每动作，怎么动）：`stride` / `pelvis_bob` / `arm_swing`，用 `--param` 调。
- **体型比例**（角色，长什么样，实例级 `state.body`，三视图共享）：`arm_length` / `leg_length` / `torso_length` / `shoulder_width` / `head_scale` / `height`（1.0=基准），用 `--body` / `set-body` 调。两者正交。

**参数优先级**（动作参数）：运行时 `--param` > 实例模板 `template_params` > 定义默认值。
**体型优先级**（角色比例）：运行时 `--body` > 实例 `body`（`new --body-template`/`--body` 设定，`set-body` 修改）> 默认 1.0。

**风格参数模板**（`workflow/templates/*.json`）：`realistic`(1.0/0.7/0.8)、`cartoon`(1.7/1.6/1.5)、`bouncy`(1.3/2.0/1.2)、`heavy`(1.6/1.8/0.9)、`light`(0.8/1.1/1.3) —— 顺序对应 stride/pelvis_bob/arm_swing。

**体型模板**（`workflow/body/*.json`）：`standard`(标准成人)、`chibi`(大头Q版)、`tall`(高挑模特)、`stocky`(矮壮力量型)。体型=角色属性，实例级共享。

## 渲染执行与 Server

- 工作流的 `run` 会调用底层 `assetslab.py`（Pillow 渲染 walk/run/idle/jump、骨架阶段）。二进制 `webflow-cli` 的**调度/管理命令独立可用**；渲染类命令在目标机无 Python 时受限（完整进程内化见 README）。
- **动作预设**：`workflow/motions/{walk,run,idle,jump}.json`，声明式（波形信号 + 关节偏移 + root + ik）。新动作 = 新 JSON。`motion check` 验证与内置姿态逐像素一致。
- **根驱动**：骨盆运动（bob/跳跃/前倾）经 `base.json` 的 `torso` 系数传导到肩/臂/头。
- **IK**：`--ik`（run/jump 预设声明）腿长恒定 + 脚落地锁定。
- **启动预览服务器**（REST API + Web 控制台，供人工通道）：
```bash
# 二进制（curl 安装 webflow-server-<linux|macos|windows>.zip）
webflow-server --port 8765 --directory <仓库>/dist --repo-root <仓库>
```

## 给 AI 的推荐执行路径

1. `new --template <风格> --body-template <体型>` 建实例 → `status` 确认 template_params + body
2. `next` 取推荐动作 → `run`（`--param` 调动作、`--body` 调体型；也可先 `set-body` 固化角色）
3. `status --json` 看该动作 `outputs`（本地图片绝对路径）+ `params`（实际所用动作+体型）；不满意可重新 `run` 调参
4. 走完 7 步 → `export.artifacts` → 制品供 Godot demo

## 约定与注意事项

- 所有命令默认在当前工作目录执行（二进制把 `run/`、`dist/` 放在 cwd）；`--json` 输出机器可读，`outputs` 返回本地图片绝对路径。
- 状态按实例持久化 `run/workflows/<id>/state.json`。
- 二进制（`webflow-cli`）的**管理/调度命令独立可用**；渲染类命令（run/stage）在目标机无 Python 时受限（完整进程内化见 README）。
- 修改骨架基座/动作后跑 `motion check` 确认与内置姿态一致。
- 渲染默认 `--renderer python`（Pillow）；`godot` 渲染器仅一致性验证。
