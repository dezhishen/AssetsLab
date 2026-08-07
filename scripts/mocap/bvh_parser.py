#!/usr/bin/env python3
"""CMU MoCap BVH 解析器 + FK 求解（纯 Python，无依赖）。

解析 BVH 的 HIERARCHY 和 MOTION，用每帧关节旋转做 FK，
返回 {joint: 每帧 [x,y,z]}（世界坐标）与关节层级。

CMU 骨架通道：根 6（Xpos Ypos Zpos + Zrot Yrot Xrot），其余 3（Zrot Yrot Xrot）。
坐标：x=左右, y=上(CMU y 向下? 需检查), z=前后。
"""
import math, re, json

class Joint:
    def __init__(self, name, offset, channels, parent=None):
        self.name = name
        self.offset = offset        # [x,y,z]
        self.channels = channels    # 通道名列表
        self.parent = parent
        self.children = []

def parse_bvh(text):
    toks = re.findall(r'[^\s{}]+|[{}\n]', text)
    pos = 0
    def next_tok():
        nonlocal pos
        while pos < len(toks) and toks[pos] in ('\n',''):
            pos += 1
        if pos >= len(toks):
            return None
        t = toks[pos]; pos += 1
        return t
    # 期待 HIERARCHY ROOT
    assert next_tok() == 'HIERARCHY'
    root_name = next_tok()
    assert root_name == 'ROOT'
    name = next_tok()
    root = Joint(name, [0,0,0], [], None)
    # 解析 { ... }
    def parse_block(joint):
        assert next_tok() == '{'
        while True:
            t = next_tok()
            if t is None: break
            if t == '}': break
            if t == 'OFFSET':
                joint.offset = [float(next_tok()), float(next_tok()), float(next_tok())]
            elif t == 'CHANNELS':
                n = int(next_tok())
                joint.channels = [next_tok() for _ in range(n)]
            elif t == 'JOINT':
                cname = next_tok()
                cj = Joint(cname, [0,0,0], [], joint)
                joint.children.append(cj)
                parse_block(cj)
            elif t == 'End':
                # End Site { OFFSET ... }
                assert next_tok() == 'Site'
                parse_block_end()
            elif t == 'MOTION':
                pos -= 1  # 回退，让主循环处理
                return
    def parse_block_end():
        assert next_tok() == '{'
        while True:
            t = next_tok()
            if t == '}': break
            # ignore OFFSET values
    parse_block(root)
    # MOTION
    assert next_tok() == 'MOTION'
    assert next_tok() == 'Frames:'
    nframes = int(next_tok())
    assert next_tok() == 'Frame'
    assert next_tok() == 'Time:'
    ft = float(next_tok())
    # 读取帧数据（每帧：根 channels + 各关节 channels，深度优先）
    frame_data = []
    for _ in range(nframes):
        row = []
        for __ in range(6 + 3*(count_joints(root)-1)):
            t = next_tok()
            if t is None: break
            row.append(float(t))
        frame_data.append(row)
    return root, nframes, ft, frame_data

def count_joints(root):
    n = 1
    for c in root.children:
        n += count_joints(c)
    return n

def flatten(root):
    out = []
    def walk(j):
        out.append(j)
        for c in j.children: walk(c)
    walk(root)
    return out

def rot_mats(frame, root):
    """每帧 → {joint: 3x3 累积旋转矩阵}（ZYX 欧拉）。"""
    mats = {}
    joints = flatten(root)
    idx = 0
    def apply(joint, parent_mat):
        nonlocal idx
        # 本关节旋转通道（根 6：前3是位移，后3是旋转）
        base = 0 if joint is root else 0
        # 从 frame 取本关节通道
        if joint is root:
            ch = frame[:6]
            rot = euler_zyx(ch[3], ch[4], ch[5])
        else:
            # 非根：3 通道 Zrot Yrot Xrot
            ch = frame[6 + 3*(idx-1): 6 + 3*idx]
            rot = euler_zyx(ch[0], ch[1], ch[2])
            idx += 1
        local = rot
        if parent_mat is None:
            mats[joint] = local
        else:
            mats[joint] = mat_mul(parent_mat, local)
        for c in joint.children:
            apply(c, mats[joint])
    apply(root, None)
    return mats

def euler_zyx(z, y, x):
    """ZYX 欧拉角(度)→旋转矩阵。"""
    zr, yr, xr = math.radians(z), math.radians(y), math.radians(x)
    cz, sz = math.cos(zr), math.sin(zr)
    cy, sy = math.cos(yr), math.sin(yr)
    cx, sx = math.cos(xr), math.sin(xr)
    Rz = [[cz,-sz,0],[sz,cz,0],[0,0,1]]
    Ry = [[cy,0,sy],[0,1,0],[-sy,0,cy]]
    Rx = [[1,0,0],[0,cx,-sx],[0,sx,cx]]
    return mat_mul(mat_mul(Rz,Ry),Rx)

def mat_mul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

def mat_vec(m,v):
    return [m[0][0]*v[0]+m[0][1]*v[1]+m[0][2]*v[2],
            m[1][0]*v[0]+m[1][1]*v[1]+m[1][2]*v[2],
            m[2][0]*v[0]+m[2][1]*v[1]+m[2][2]*v[2]]

def fk_positions(root, frame):
    """FK：算每关节世界位置。返回 {joint_name: [x,y,z]}。"""
    mats = rot_mats(frame, root)
    joints = flatten(root)
    pos = {}
    for j in joints:
        m = mats[j]
        off = j.offset
        if j is root:
            pos[j.name] = [frame[0], frame[1], frame[2]]  # 根位移
        else:
            ppos = pos[j.parent.name]
            v = mat_vec(m, off)
            pos[j.name] = [ppos[0]+v[0], ppos[1]+v[1], ppos[2]+v[2]]
    return pos

def load_bvh(path):
    with open(path) as f:
        text = f.read()
    root, nframes, ft, data = parse_bvh(text)
    return root, nframes, ft, data
