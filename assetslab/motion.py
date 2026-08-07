#!/usr/bin/env python3
"""AssetsLab — 3D 动作 DSL 求值器（数据驱动，无 2D 遗留）。

3D 动作（species/<id>/actions3d/*.json）用 offsets3d / root3d / ik3d + signals
描述每帧关节运动。本模块只提供通用表达式求值（_eval）与参数解析
（_build_signals / _resolve_params），供 skeleton3d.pose_3d 与
verify_motions3d 使用。所有定义均来自动作 JSON 数据，无任何硬编码。

3D 姿势求值（pose_3d / IK / 层级跟随 / 刚性传播）在 assetslab/skeleton3d.py。
"""
from __future__ import annotations

import math


class MotionError(Exception):
    """Raised for invalid motion data or expressions."""


def _eval(expr, ctx: dict):
    """Evaluate a motion expression against a context dict.

    ``ctx`` keys: params, index, frame_count, phase, signals (name -> fn(ctx)).
    """
    if isinstance(expr, bool):
        return 1.0 if expr else 0.0
    if isinstance(expr, (int, float)):
        return float(expr)
    if isinstance(expr, str):
        return ctx["signals"][expr](ctx)
    if isinstance(expr, dict):
        if len(expr) != 1:
            raise MotionError(f"expression must be a single-op dict: {expr!r}")
        op, arg = next(iter(expr.items()))
        if op == "param":
            return float(ctx["params"][arg])
        if op == "phase":
            return ctx["phase"]
        if op == "index":
            return float(ctx["index"])
        if op == "frame_count":
            return float(ctx["frame_count"])
        if op == "const":
            return float(arg)
        if op == "signal":
            return ctx["signals"][arg](ctx)
        if op == "sin":
            return math.sin(_eval(arg, ctx))
        if op == "cos":
            return math.cos(_eval(arg, ctx))
        if op == "neg":
            return -_eval(arg, ctx)
        if op == "rect":
            return max(0.0, _eval(arg, ctx))
        if op == "abs":
            return abs(_eval(arg, ctx))
        if op == "add":
            return sum(_eval(a, ctx) for a in arg)
        if op == "sub":
            return _eval(arg[0], ctx) - _eval(arg[1], ctx)
        if op == "mul":
            out = 1.0
            for a in arg:
                out *= _eval(a, ctx)
            return out
        if op == "table":
            return float(arg[ctx["index"] % len(arg)])
        raise MotionError(f"unknown expression op: {op!r}")
    raise MotionError(f"cannot evaluate: {expr!r}")


def _build_signals(motion: dict) -> dict:
    """Return {signal_name: fn(ctx)} for every named signal in the preset."""
    defined = motion.get("signals", {})
    return {name: (lambda expr: (lambda c: _eval(expr, c)))(expr)
            for name, expr in defined.items()}


def _resolve_params(motion: dict, overrides: dict) -> dict:
    """解析动作参数：只接受动作 params 里定义的名字（数据驱动，无白名单）。"""
    defaults = {name: spec.get("default", 0.0)
                for name, spec in motion.get("params", {}).items()}
    merged = dict(defaults)
    for key, value in (overrides or {}).items():
        if key in defaults:
            merged[key] = float(value)
        else:
            raise MotionError(f"unknown motion param: {key}")
    return merged
