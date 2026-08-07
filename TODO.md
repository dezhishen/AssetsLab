# AssetsLab — 任务交接 / TODO

> 本文件用于项目内交接：新会话/伙伴接手时先读本文件 + `README_ZH.md`。
> 当前主线：**3D 动作系统（CMU 动捕数据驱动）+ Web 前端预览 + Godot demo 验证**。

## 一、当前主线（最近会话）

**骨骼与 walk 完全按真实 CMU 动捕数据驱动**（subject16, `16_15.bvh`）

- 已完成：
  - 骨骼 `default.json` positions_3d 按 CMU OFFSET 重建，骨长比例与真实数据精确一致
  - `walk3d` 16 帧全关节旋转 table 完全照搬 CMU 通道值 + 真实骨盆位移
  - 引擎修复：FK 分支跳过 rigid_chains、elbow 检查改解剖学 shoulder-elbow-wrist、BVH FK 用父累积旋转
  - `verify_motions3d.py` walk 8 项全 PASS
  - 前端动作预览封装 `MotionPreview.vue`（播放 + 导出 GIF，后端 `gif=1`）
  - 清理过时内容：skins / packaging / build / webflow 发布链 / 旧参考资产

## 二、当前结构（清理后）

| 路径 | 说明 |
|---|---|
| `assetslab/` | 3D 动作引擎（skeleton3d.py FK/IK、motion.py DSL、server.py HTTP API）+ web 前端（Vue 预览） |
| `assetslab/species/human/` | 人类骨骼（skeleton.json / default.json）+ actions3d（当前仅 walk3d） |
| `scripts/mocap/` | CMU 动捕工具链：bvh_parser / rebuild_skeleton_cmu / extract_kin / compare_motion |
| `scripts/verify_motions3d.py` | 3D 动作验证工具（8 项检查） |
| `scripts/build_demo.sh/.bat` | Godot demo 运行脚本（基于 dist 制品） |
| `prototype/` | **Godot 4.7 工程（保留）**：运行时脚本、分层资产、无头测试 |

## 三、下一步（待办）

1. **[P0] run / jump 同样用 CMU 真实数据**（`16_35.bvh` run、`16_01.bvh` jump），方法同 walk（`rebuild_skeleton_cmu.py` 扩展或新增生成）。
2. **[P1] 其他动作**（idle 等）按真实/合理数据补全。
3. **[P2] Godot demo 接入 3D 动作**：确认 `prototype/` 消费 `dist/<id>/` 制品的流程（`scripts/build_demo.sh`）。
4. **[P2] Web 前端**：预览交互打磨、多动作切换。

## 四、关键命令

```bash
# 验证 3D 动作
.venv/bin/python scripts/verify_motions3d.py --species human --action walk3d

# CMU 真实骨骼/walk 重建（数据驱动，勿手工改 JSON）
.venv/bin/python scripts/mocap/rebuild_skeleton_cmu.py --inspect   # 查看 CMU 数据特征
.venv/bin/python scripts/mocap/rebuild_skeleton_cmu.py --skeleton  # 重建 default.json positions_3d
.venv/bin/python scripts/mocap/rebuild_skeleton_cmu.py --walk      # 重建 walk3d.json（真实旋转）

# 后端 API 服务器（Web 前端预览）
.venv/bin/python assetslab/server.py --port 8765
```

## 五、已知坑 / 约定

1. **数据驱动**：骨骼/动作参数一律从真实 CMU BVH 提取，不要手工设计参数（用户明确要求）。
2. **FK 语义**：位置用父累积旋转（不含自身）；FK 分支跳过 rigid_chains（避免覆盖真实脚位）。
3. **循环走**：root3d.z 移除（原地走，腿步幅真实），否则周期 wrap 会跳变。
4. **周期检测**：完整步态周期 = 同侧着地（间隔 2），自动选姿势差最小（walk 用 139 帧，差 11.4°）。
5. **elbow 检查**：用解剖学 shoulder-elbow-wrist 三点（walk 肘屈 18~35° 匹配真实）。
6. **环境**：用 `.venv/`（Pillow 12.3.0）；纯 Python（无 numpy/scipy）。
