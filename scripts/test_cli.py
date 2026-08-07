#!/usr/bin/env python3
"""AssetsLab CLI 流程化测试（数据隔离，不污染真实 data/）。

覆盖物种 / 动作 / 预设 / 渲染 的完整生命周期（创建→验证→修改→删除），
通过 subprocess 调用真实 CLI 进程（python -m assetslab.cli），断言退出码与输出。

运行：
    .venv/bin/python scripts/test_cli.py

依赖：仅标准库（unittest），无第三方依赖。
数据目录：test-data-cli/（复制自 data/species，测试后清理；与 E2E 的 test-data/ 分开）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable
DATA_DIR = REPO / "test-data-cli"  # CLI 测试专用数据目录（隔离）
OUT_DIR = REPO / "test-output" / "cli"  # 渲染输出

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
GIF_MAGIC = b"GIF89a"


def cli(*args: str) -> str:
    """调用 CLI（--data-dir 隔离），断言退出码 0，返回 stdout。"""
    r = subprocess.run(
        [PY, "-m", "assetslab.cli", "--data-dir", str(DATA_DIR), *args],
        capture_output=True, text=True, cwd=REPO,
    )
    if r.returncode != 0:
        raise AssertionError(
            f"CLI 失败: assetslab.cli {' '.join(args)}\n"
            f"--- stdout ---\n{r.stdout}\n--- stderr ---\n{r.stderr}"
        )
    return r.stdout


def cli_fail(*args: str) -> subprocess.CompletedProcess:
    """调用 CLI 但期望失败（退出码非 0），返回 CompletedProcess 供断言。"""
    return subprocess.run(
        [PY, "-m", "assetslab.cli", "--data-dir", str(DATA_DIR), *args],
        capture_output=True, text=True, cwd=REPO,
    )


def _species_create(sid: str, title: str = "CLI 测试物种") -> dict:
    return {
        "species_id": sid, "schema": "assetslab_species_v1", "title": title,
        "description": "CLI 流程化测试", "joints": {"core": ["root", "mid"]},
        "bones_3d": [["root", "mid"]], "chains": {"main": ["root", "mid"]},
        "param_chains": {}, "follow_chains": {}, "follow_config": {},
    }


def _action_create(aid: str, title: str = "CLI 测试动作") -> dict:
    return {
        "schema": "assetslab_motion3d_v1", "motion_id": aid, "title": title,
        "description": "", "species": "human", "frame_count": 8,
        "params": {}, "root3d": {"dy": {"phase": True}}, "offsets3d": {}, "ik3d": {},
    }


def _preset_create(pid: str, title: str = "CLI 测试预设", body: dict | None = None) -> dict:
    return {
        "schema": "assetslab_preset_v1", "preset_id": pid, "species": "human",
        "title": title, "description": "", "body": body or {"head_scale": 1.2}, "actions": {},
    }


class TestCliWorkflow(unittest.TestCase):
    """CLI 全流程测试：各用例相互独立（自建自删），可任意顺序执行。"""

    @classmethod
    def setUpClass(cls):
        # 准备隔离数据目录：复制 data/species，presets 清空
        shutil.rmtree(DATA_DIR, ignore_errors=True)
        shutil.copytree(REPO / "data" / "species", DATA_DIR / "species")
        (DATA_DIR / "presets").mkdir(parents=True, exist_ok=True)
        shutil.rmtree(OUT_DIR, ignore_errors=True)
        OUT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(DATA_DIR, ignore_errors=True)
        shutil.rmtree(OUT_DIR, ignore_errors=True)

    # ------------------------------------------------------------------
    # 物种 CRUD 流程
    # ------------------------------------------------------------------

    def test_species_crud(self):
        # list 包含 human（内置物种）
        out = cli("species", "list")
        self.assertIn("human", out)

        # show 内置物种
        d = json.loads(cli("species", "show", "human"))
        self.assertEqual(d["species_id"], "human")
        self.assertIn("bones_3d", d)

        # default 读取（内置 human 有 default.json：positions_3d 体型）
        def_ = json.loads(cli("species", "default", "human"))
        self.assertIn("positions_3d", def_)

        # create 新物种 → list 出现
        sid = "cli_sp"
        cli("species", "create", "--json", json.dumps(_species_create(sid)))
        self.assertIn(sid, cli("species", "list"))

        # show 验证
        d = json.loads(cli("species", "show", sid))
        self.assertEqual(d["species_id"], sid)
        self.assertEqual(d["title"], "CLI 测试物种")

        # update 改名 → show 验证
        cli("species", "update", sid, "--json",
            json.dumps(_species_create(sid, title="CLI 物种改名")))
        self.assertEqual(json.loads(cli("species", "show", sid))["title"], "CLI 物种改名")

        # delete → list 消失
        cli("species", "delete", sid)
        self.assertNotIn(sid, cli("species", "list"))

    # ------------------------------------------------------------------
    # 动作 CRUD 流程
    # ------------------------------------------------------------------

    def test_action_crud(self):
        # list 包含 walk3d（内置）
        out = cli("action", "list")
        self.assertIn("walk3d", out)

        # show 内置动作
        d = json.loads(cli("action", "show", "human", "walk3d"))
        self.assertEqual(d["motion_id"], "walk3d")
        self.assertEqual(d["species"], "human")
        self.assertGreater(d["frame_count"], 1)

        # create 新动作 → list 出现
        aid = "cli_act"
        cli("action", "create", "human", "--json", json.dumps(_action_create(aid)))
        self.assertIn(aid, cli("action", "list"))

        # show 验证
        d = json.loads(cli("action", "show", "human", aid))
        self.assertEqual(d["motion_id"], aid)

        # update 改名 → show 验证
        cli("action", "update", "human", aid, "--json",
            json.dumps(_action_create(aid, title="CLI 动作改名")))
        self.assertEqual(json.loads(cli("action", "show", "human", aid))["title"], "CLI 动作改名")

        # delete → show 失败
        cli("action", "delete", "human", aid)
        r = cli_fail("action", "show", "human", aid)
        self.assertNotEqual(r.returncode, 0)

    # ------------------------------------------------------------------
    # 预设 CRUD 流程
    # ------------------------------------------------------------------

    def test_preset_crud(self):
        # list 空
        out = cli("preset", "list")
        self.assertNotIn("cli_preset", out)

        # new human → schema（体型参数 + 动作参数）
        d = json.loads(cli("preset", "new", "human"))
        self.assertEqual(d["schema"], "assetslab_preset_v1")
        self.assertEqual(d["species"], "human")
        self.assertIn("body", d)
        self.assertIn("actions", d)
        self.assertIn("head_scale", d["body"])

        # create → list 出现
        pid = "cli_preset"
        cli("preset", "create", "--json", json.dumps(_preset_create(pid)))
        self.assertIn(pid, cli("preset", "list"))

        # show 验证：值已保存 + schema_info 派生（body_params 不落盘）
        d = json.loads(cli("preset", "show", pid))
        self.assertEqual(d["preset_id"], pid)
        self.assertEqual(d["body"]["head_scale"], 1.2)
        self.assertIn("schema_info", d)
        self.assertIn("body_params", d["schema_info"])

        # update 改 title/body → show 验证
        cli("preset", "update", pid, "--json",
            json.dumps(_preset_create(pid, title="CLI 预设改名", body={"head_scale": 1.5})))
        d = json.loads(cli("preset", "show", pid))
        self.assertEqual(d["title"], "CLI 预设改名")
        self.assertEqual(d["body"]["head_scale"], 1.5)

        # delete → list 消失
        cli("preset", "delete", pid)
        self.assertNotIn(pid, cli("preset", "list"))

    # ------------------------------------------------------------------
    # 渲染流程（skeleton / motion / preset / live）
    # ------------------------------------------------------------------

    def test_render(self):
        # skeleton → PNG（校验魔数）
        png = OUT_DIR / "skeleton.png"
        cli("render", "skeleton", "human", "--yaw", "45", "--out", str(png))
        self.assertEqual(png.read_bytes()[:8], PNG_MAGIC)

        # motion → GIF（校验魔数）
        gif = OUT_DIR / "walk.gif"
        cli("render", "motion", "walk3d", "--species", "human", "--gif", "--out", str(gif))
        self.assertEqual(gif.read_bytes()[:6], GIF_MAGIC)

        # preset：先创建 → 渲染骨架 PNG
        pid = "cli_render_preset"
        cli("preset", "create", "--json", json.dumps(_preset_create(pid)))
        skel = OUT_DIR / "preset_skel.png"
        cli("render", "preset", pid, "--out", str(skel))
        self.assertEqual(skel.read_bytes()[:8], PNG_MAGIC)

        # preset + action → GIF（应用体型 + 动作）
        walk = OUT_DIR / "preset_walk.gif"
        cli("render", "preset", pid, "--action", "walk3d", "--gif", "--out", str(walk))
        self.assertEqual(walk.read_bytes()[:6], GIF_MAGIC)

        # live：不落盘实时渲染（body 参数）
        live = OUT_DIR / "live.png"
        cli("render", "live", "--species", "human", "--body", "head_scale=1.2", "--out", str(live))
        self.assertEqual(live.read_bytes()[:8], PNG_MAGIC)

        # 清理
        cli("preset", "delete", pid)

    # ------------------------------------------------------------------
    # 错误处理
    # ------------------------------------------------------------------

    def test_error_handling(self):
        # 不存在的物种 → 退出码非 0 + stderr 报错
        r = cli_fail("species", "show", "not_exists")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not found", r.stderr)

        # preset create 缺 preset_id → 失败
        r = cli_fail("preset", "create", "--json", json.dumps({"species": "human"}))
        self.assertNotEqual(r.returncode, 0)

        # render 缺 --out → 失败（argparse required）
        r = cli_fail("render", "skeleton", "human")
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
