# AssetsLab — 皮肤任务交接 / TODO

> 本文件用于项目内交接：新会话/伙伴接手时先读本文件 + `SKINNING.md` + `README_ZH.md`。
> 当前主线：**写实风格女性角色（female）打磨，目标是「能成为模特」的手游素材**。

---

## 一、当前主线（最新会话进行中）

**写实女性 `skins/female/`** — 生成器 `workflow/tools/build_female_skin.py`

- 目标：人类女性解剖比例、细节完善、五官清晰、侧视与发型到位，最终「能成为模特」。
- 已完成：
  - 模特体型（head 0.88 / neck 0.6 / torso 0.95 / shoulder 0.88 / 四肢 0.95 / 腿 1.15）
  - **A 字连衣裙**（裙摆向下延伸盖住大腿上部，腿从裙下接出；靠 skin.json `layer_order` 让裙子盖住腿）
  - **高跟鞋**（尖头细跟）
  - 胯宽收窄（裙摆半宽 0.58ws）
  - 详细五官（正面+侧视）：杏眼/弯眉/小鼻/唇/腮红
  - 长直发：正面中分刘海+鬓发、**侧视长垂发沿背流下**、背面满发
- 下次会话先做：**目检 female 三视图（`showcase.html`），按用户反馈继续微调**（裙摆长度/宽度、鞋跟高度、发型长度/卷、领口、配色、配饰如耳环项链）。

## 二、皮肤清单与状态

| 皮肤 | 生成器/风格 | 状态 |
|---|---|---|
| `female` | build_female_skin.py · 写实平滑 | **打磨中（当前主线）** |
| `chibi` | build_chibi_skin.py · 像素 Q 版 | 已完成（大头大眼 1px 描边，可手游） |
| `mannequin` | build_mannequin_skin.py v2 平滑 | 已完成（无关节球） |
| `elf` | build_mannequin_skin.py v2 平滑 | 已完成（精灵，金发） |
| `mannequin_swordswoman` | v2 | 有皮肤包，未用 v2 重建 |
| `orc`/`human_warrior`/`undead`/`dwarf` | 旧版（平滑 v2 之前的） | **待批量重建为 v2**（无关节球） |
| `skeleton` | legacy 预烘焙 | 旧格式，兼容保留 |

> `skins/*/preview/` 是 `skin.py render` 的输出（git 忽略）；运行必需仅 `skin.json` + 39 部件 PNG。

## 三、下一步（待办，按优先级）

1. **[P0] female 继续打磨**（当前主线）——按用户反馈调裙摆/发型/鞋/配色/配饰；每改一次跑：
   `build_female_skin.py --out female` → `skin.py render walk/idle … --skin female` → 刷新 showcase。
2. **[P1] 批量重建旧皮肤为 v2 精细版**（去掉关节球）：
   `orc / human_warrior / undead / dwarf / mannequin_swordswoman`，用 `build_mannequin_skin.py --palette <id> --out <id> --body …`，再重渲染 preview。
3. **[P1] 每个皮肤重新烘焙 demo 制品**：`export_skin_demo.py --skin <id>` → `dist/<id>/`（64×64 分层帧 + manifest + 四向 GIF）。
4. **[P2] showcase.html 补齐新皮肤卡片**（female 已有；chibi 已有；批量重建后更新旧卡）。
5. **[P2] Godot demo 验证**：`godot --path prototype -- --artifacts dist/<id>`（headless 时 grep `ARTIFACTS_LOADED`）。
6. **[P2] 预览服务器**：`.venv/bin/python workflow/tools/lan_preview_server.py --port 8765 --directory dist --repo-root <repo>`；静态展示页 `python3 -m http.server 8123 --bind 127.0.0.1` → `http://127.0.0.1:8123/skins/showcase.html`。

## 四、关键命令（都在仓库根，用 `.venv/bin/python`）

```bash
# 生成皮肤包（→ skins/<id>/）
.venv/bin/python workflow/tools/build_female_skin.py --out female [--hair R,G,B] [--skin R,G,B] [--body thigh_length=1.2]
.venv/bin/python workflow/tools/build_chibi_skin.py --out chibi [--hair R,G,B] [--body ...]
.venv/bin/python workflow/tools/build_mannequin_skin.py --palette orc --out orc --body head_scale=1.15 --body shoulder_width=1.4

# 渲染预览（→ skins/<id>/preview/<id>_<motion>_<view>.gif + frame PNG）
.venv/bin/python workflow/tools/skin.py render walk --view front --stage arms --skin female
.venv/bin/python workflow/tools/skin.py render idle --view front --stage arms --skin female

# 校验 + 烘焙制品（→ dist/<id>/，供 Godot demo 消费）
.venv/bin/python workflow/tools/skin.py verify --skin female
.venv/bin/python workflow/tools/export_skin_demo.py --skin female

# 展示页服务器（本地浏览）
python3 -m http.server 8123 --bind 127.0.0.1   # → http://127.0.0.1:8123/skins/showcase.html
```

## 五、架构速览（细节见 SKINNING.md）

- **皮肤 = 部件图 + 绑定**：`skins/<id>/` 下 13 层 × 3 视图（front/side/back）PNG + `skin.json`（bindings、body 体型、layers、可选 `layer_order`）。
- **锚点约定**：锚点 = 部件图中心（=关节）；肢体段从中心沿 +x 延伸，`rotate_child` 绕锚点旋转到 关节→子关节 方向 → rest 天然贴合。
- **三个生成器**：`build_mannequin_skin.py`（v2 平滑，SS=4 抗锯齿+渐变+描边）、`build_chibi_skin.py`（像素 Q 版）、`build_female_skin.py`（写实女性，基于 v2 渲染工具）。
- **渲染/烘焙**：`skin.py`（实时蒙皮合成）、`export_skin_demo.py`（烘焙成 demo 7 层 64×64 帧）。
- **体型参数**（apply_proportions）：`head_scale / neck_length / torso_length / shoulder_width / upper_arm_length / forearm_length / thigh_length / shin_length`，作用于 base.json 骨架。

## 六、已知坑 / 约定（重要，别重复踩）

1. **head_scale 下巴锚定**（motion.py `apply_proportions`）：头大小只放大头部、不拉长脖子；脖子长度唯一由 `neck_length` 决定。别再改回“头随 head_scale 上移”。
2. **四肢比例已协调**：腿的 thigh_length/shin_length 不再互相抵消（膝盖从髋缩放、脚从新膝盖沿原小腿方向缩放）。改 apply_proportions 会同时影响部件烘焙与渲染（一致、安全），但 **elf 等需重生成**。
3. **关节球已全部删除**：任何生成器不要再画关节球（“骨骼人偶”凸点）。
4. **皮肤 `layer_order`**：skin.json 可声明覆盖层序（female 靠它让裙子盖住腿）。默认 ZONES 序 = 头/颈/臂 → 躯干 → 腿 → 脚。
5. **像素皮肤**（skin.json `"style":"pixel"`）：skin.py / export_skin_demo 据此用 NEAREST 保持像素锐利；平滑皮肤用 BICUBIC/LANCZOS。
6. **draw_torso 的 c 必须 `size*ss//2`（SS 坐标）**，写成 `size//2` 会致躯干错位变小（female 生成器踩过）。
7. **侧视连接**：骨架 side 肩/髋对称在中心 ±18px；chibi 用「加宽侧视躯干(ws=42)」让连接点视觉上在躯体中间；不要改 base.json side 关节（walk 偏移 add[±18/±30] 校准到骨架，改了会连锁破坏走路 + motion check）。
8. **渲染预览默认取 skin.body**：`skin.py render` 未传 `--body` 时自动用皮肤自带体型，避免“放大部件贴到未缩放骨架”的缝隙。
9. **`verify` 第一个位置参数是 atlas**（非 skin）：正确用法 `skin.py verify --skin <id>`。
10. **环境**：用 `.venv/`（Pillow 12.3.0）；预览服务器改代码后必须重启进程。
