#!/usr/bin/env python3
"""从 CMU MoCap BVH 提取真实骨架与动作数据。

数据驱动核心：不手工设计参数，全部从真实 BVH 提取。
用法:
  python rebuild_skeleton_cmu.py --inspect   # 打印骨架骨长 + 动作数据特征
  python rebuild_skeleton_cmu.py --skeleton  # 生成 default.json positions_3d（CMU 比例）
  python rebuild_skeleton_cmu.py --walk      # 生成 walk3d.json（真实旋转 table）
"""
import math, re, json, sys
from pathlib import Path

BVH = Path('/tmp/16_15.bvh')
WE = Path('/home/sdniu/github/assets-lab')
sys.path.insert(0, str(WE))
CENTER_X = 480.0
FLOOR_Y = 470.0

class Joint:
    def __init__(self, name, offset, channels, parent=None):
        self.name, self.offset, self.channels = name, offset, channels
        self.parent, self.children = parent, []

def parse_bvh(text):
    toks = re.findall(r'[^\s{}]+|[{}\n]', text)
    pos = [0]
    def nxt():
        while pos[0] < len(toks) and toks[pos[0]] in ('\n',''):
            pos[0] += 1
        if pos[0] >= len(toks): return None
        t = toks[pos[0]]; pos[0] += 1
        return t
    assert nxt() == 'HIERARCHY'; assert nxt() == 'ROOT'
    name = nxt()
    root = Joint(name, [0,0,0], [], None)
    def parse_block(j):
        assert nxt() == '{'
        while True:
            t = nxt()
            if t is None or t == '}': break
            if t == 'OFFSET': j.offset = [float(nxt()), float(nxt()), float(nxt())]
            elif t == 'CHANNELS': j.channels = [nxt() for _ in range(int(nxt()))]
            elif t == 'JOINT':
                c = Joint(nxt(), [0,0,0], [], j); j.children.append(c); parse_block(c)
            elif t == 'End': assert nxt() == 'Site'; parse_end()
            elif t == 'MOTION': pos[0] -= 1; return
    def parse_end():
        assert nxt() == '{'
        while True:
            t = nxt()
            if t == '}': break
    parse_block(root)
    assert nxt() == 'MOTION'
    assert nxt() == 'Frames:'; nf = int(nxt())
    assert nxt() == 'Frame'; assert nxt() == 'Time:'; ft = float(nxt())
    n_joints = count(root)
    data = []
    for _ in range(nf):
        data.append([float(nxt()) for _ in range(6 + 3*(n_joints-1))])
    return root, nf, ft, data

def count(j): return 1 + sum(count(c) for c in j.children)
def flatten(root):
    out = []
    def w(j): out.append(j); [w(c) for c in j.children]
    w(root); return out
def mat_mul(a,b):
    return [[sum(a[i][k]*b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
def mat_vec(m,v):
    return [m[0][0]*v[0]+m[0][1]*v[1]+m[0][2]*v[2],
            m[1][0]*v[0]+m[1][1]*v[1]+m[1][2]*v[2],
            m[2][0]*v[0]+m[2][1]*v[1]+m[2][2]*v[2]]
def euler_zyx(z,y,x):
    zr,yr,xr = math.radians(z),math.radians(y),math.radians(x)
    cz,sz,cy,sy,cx,sx = math.cos(zr),math.sin(zr),math.cos(yr),math.sin(yr),math.cos(xr),math.sin(xr)
    Rz=[[cz,-sz,0],[sz,cz,0],[0,0,1]]
    Ry=[[cy,0,sy],[0,1,0],[-sy,0,cy]]
    Rx=[[1,0,0],[0,cx,-sx],[0,sx,cx]]
    return mat_mul(mat_mul(Rz,Ry),Rx)

def frame_channels(root, frame):
    joints = flatten(root)
    out = {}
    out[root.name] = {'pos':[frame[0],frame[1],frame[2]], 'rot':[frame[3],frame[4],frame[5]]}
    idx = 0
    for j in joints:
        if j is root: continue
        out[j.name] = {'rot':[frame[6+3*idx],frame[7+3*idx],frame[8+3*idx]]}
        idx += 1
    return out

def fk_world(root, frame):
    joints = flatten(root)
    ch = frame_channels(root, frame)
    pos = {}
    def walk(j, pmat):
        rot = ch[j.name]['rot']
        local = euler_zyx(rot[0],rot[1],rot[2])
        if j is root:
            pos[j.name] = ch[j.name]['pos']
            R = local
        else:
            # 位置用父累积旋转 pmat（不含自身旋转），BVH 标准
            v = mat_vec(pmat, j.offset)
            pos[j.name] = [pos[j.parent.name][i]+v[i] for i in range(3)]
            R = mat_mul(pmat, local)
        for c in j.children: walk(c, R)
    walk(root, None)
    return pos

def load_cmu():
    return parse_bvh(BVH.read_text())

def build_cmu_base(root):
    pos = {}
    def walk(j):
        if j.parent is None: pos[j.name] = [0.0,0.0,0.0]
        else: pos[j.name] = [pos[j.parent.name][i]+j.offset[i] for i in range(3)]
        for c in j.children: walk(c)
    walk(root)
    return pos

def bone_lengths(root):
    return {j.name: (math.hypot(*j.offset), j.offset)
            for j in flatten(root) if j.parent is not None}

def mid(a,b,t=0.5): return [a[i]+(b[i]-a[i])*t for i in range(3)]

def scale_factor(base):
    toe = base['LeftToeBase'][1]
    head_top = base['Head'][1] + 1.679
    height = head_top - toe
    target = FLOOR_Y - 90.0
    return target / height

def we(base, jname, S, pelvis_we):
    x,y,z = base[jname]
    return [CENTER_X - x*S, pelvis_we - y*S, z*S]

def gen_positions_3d(base, S, pelvis_we):
    J = {}
    J['pelvis'] = [CENTER_X, pelvis_we, 0.0]
    J['waist']  = we(base,'Spine',S,pelvis_we)
    J['chest']  = we(base,'Spine1',S,pelvis_we)
    J['abdomen']= mid(J['pelvis'], J['waist'], 0.5)
    J['sternum']= mid(J['waist'], J['chest'], 0.5)
    J['neck']   = we(base,'Neck1',S,pelvis_we)
    J['head']   = we(base,'Head',S,pelvis_we)
    J['jaw']    = mid(J['neck'], J['head'], 0.55)
    for side, (h,k,a,t) in {
        'left': ('LeftUpLeg','LeftLeg','LeftFoot','LeftToeBase'),
        'right': ('RightUpLeg','RightLeg','RightFoot','RightToeBase'),
    }.items():
        hp = we(base,h,S,pelvis_we); kp = we(base,k,S,pelvis_we)
        ap = we(base,a,S,pelvis_we); tp = we(base,t,S,pelvis_we)
        J[f'hip_{side}'] = hp; J[f'knee_{side}'] = kp; J[f'ankle_{side}'] = ap; J[f'toe_{side}'] = tp
        J[f'heel_{side}'] = [ap[0], ap[1]+0.7*S, ap[2]-1.5*S]
        J[f'foot_{side}'] = mid(ap, tp, 0.55)
    for side, (s,e,w,p) in {
        'left': ('LeftArm','LeftForeArm','LeftHand','LeftHandIndex1'),
        'right': ('RightArm','RightForeArm','RightHand','RightHandIndex1'),
    }.items():
        sp = we(base,s,S,pelvis_we); ep = we(base,e,S,pelvis_we)
        wp = we(base,w,S,pelvis_we); pp = we(base,p,S,pelvis_we)
        J[f'shoulder_{side}'] = sp; J[f'elbow_{side}'] = ep; J[f'wrist_{side}'] = wp; J[f'palm_{side}'] = pp
        sign = -1 if side=='left' else 1
        J[f'finger_{side}'] = [pp[0]+sign*0.4*S, pp[1], pp[2]]
        J[f'clavicle_{side}'] = mid(J['chest'], sp, 0.5)
    J['rib_upper_left']  = [J['chest'][0]-0.8*S, J['chest'][1], J['chest'][2]+0.2*S]
    J['rib_upper_right'] = [J['chest'][0]+0.8*S, J['chest'][1], J['chest'][2]+0.2*S]
    J['rib_lower_left']  = [J['sternum'][0]-0.8*S, J['sternum'][1], J['sternum'][2]+0.2*S]
    J['rib_lower_right'] = [J['sternum'][0]+0.8*S, J['sternum'][1], J['sternum'][2]+0.2*S]
    return J

def write_skeleton():
    root, nf, ft, data = load_cmu()
    base = build_cmu_base(root)
    S = scale_factor(base)
    pelvis_we = FLOOR_Y - abs(base['LeftToeBase'][1])*S
    J = gen_positions_3d(base, S, pelvis_we)
    print(f"S={S:.3f}  pelvis_we={pelvis_we:.1f}  脚趾底 y={J['toe_left'][1]:.1f} (目标470)")
    print(f"身高: 头 {J['head'][1]:.0f} → 脚趾 {J['toe_left'][1]:.0f} = {J['toe_left'][1]-J['head'][1]:.0f}px")
    def L(a,b): return math.dist(a,b)
    parents = {c.name:p.name for p in flatten(root) for c in p.children}
    pairs = [('大腿','hip_left','knee_left','LeftLeg'),('小腿','knee_left','ankle_left','LeftFoot'),
             ('上臂','shoulder_left','elbow_left','LeftForeArm'),('前臂','elbow_left','wrist_left','LeftHand'),
             ('髋宽','pelvis','hip_left','LeftUpLeg'),('肩宽','chest','shoulder_left','LeftArm'),
             ('躯干','pelvis','chest','Spine1'),('颈','chest','neck','Neck1')]
    print("\n骨长对比 (我们px vs CMU*S):")
    for label,a,b,cmuj in pairs:
        cmu_len = math.dist(base[cmuj], base[parents[cmuj]])
        print(f"  {label}: 我们 {L(J[a],J[b]):6.1f}px  vs CMU {cmu_len*S:6.1f}px")
    p = WE/'assetslab/species/human/default.json'
    d = json.loads(p.read_text(encoding='utf-8'))
    d['positions_3d'] = {k: [round(v[0],2),round(v[1],2),round(v[2],2)] for k,v in J.items()}
    d['head_radius'] = round(1.679*S/2, 1)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print("\n已写 default.json positions_3d (CMU 真实比例)")

NAMES = ['LeftUpLeg','LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot',
         'Spine','Spine1','Neck1','Head','LeftArm','LeftForeArm','LeftHand',
         'RightArm','RightForeArm','RightHand']

# CMU 关节旋转 → 我们关节（镜像：x、y 取反，z 同）
ROT_MAP = {
    'LeftUpLeg':'hip_left','LeftLeg':'knee_left','LeftFoot':'ankle_left','LeftToeBase':'toe_left',
    'RightUpLeg':'hip_right','RightLeg':'knee_right','RightFoot':'ankle_right','RightToeBase':'toe_right',
    'Spine':'waist','Spine1':'chest','Neck1':'neck','Head':'head',
    'LeftArm':'shoulder_left','LeftForeArm':'elbow_left','LeftHand':'wrist_left','LeftHandIndex1':'palm_left',
    'RightArm':'shoulder_right','RightForeArm':'elbow_right','RightHand':'wrist_right','RightHandIndex1':'palm_right',
    'Hips':'pelvis',
}

def find_walk_cycle(root, data, nf, min_gap=40):
    """找完整步行周期：LeftToeBase y 局部最小（左脚着地），相邻两次(间隔>min_gap) = 一个周期。"""
    toe_idx = {j.name:n for n,j in enumerate(flatten(root))}['LeftToeBase'] - 1
    toe_y = [data[i][6+3*toe_idx+1] for i in range(nf)]
    cand = [i for i in range(2, nf-2)
            if toe_y[i] < toe_y[i-1] and toe_y[i] < toe_y[i-2]
            and toe_y[i] <= toe_y[i+1] and toe_y[i] <= toe_y[i+2]]
    # 局部最小中选全局下包络（间隔够大的才是一次真正着地）
    strikes = []
    for i in cand:
        if strikes and i - strikes[-1] < min_gap:
            # 取更低的一个
            if toe_y[i] < toe_y[strikes[-1]]:
                strikes[-1] = i
        else:
            strikes.append(i)
    return strikes, toe_y

def write_walk():
    root, nf, ft, data = load_cmu()
    base = build_cmu_base(root)
    S = scale_factor(base)
    pelvis_we = FLOOR_Y - abs(base['LeftToeBase'][1])*S
    strikes, toe_y = find_walk_cycle(root, data, nf)
    # 选同侧着地(完整周期)中姿势差最小的对 → 最严格周期
    jidx = {j.name:n for n,j in enumerate(flatten(root))}
    def pose_vec(fr):
        ch = frame_channels(root, data[fr]); v=[]
        for cmu in ['LeftUpLeg','LeftLeg','LeftFoot','RightUpLeg','RightLeg','RightFoot',
                    'Spine','Spine1','Neck1','Head','LeftArm','LeftForeArm','LeftHand',
                    'RightArm','RightForeArm','RightHand','Hips']:
            v += list(ch[cmu]['rot'])
        return v
    best = None
    for i in range(len(strikes)-2):
        a, b = strikes[i], strikes[i+2]
        d = math.dist(pose_vec(a), pose_vec(b))
        if best is None or d < best[0]:
            best = (d, a, b)
    d0, c0, c1 = best
    print(f"左脚着地帧: {strikes}")
    print(f"最优周期 [{c0},{c1}] 共 {c1-c0} 帧, 姿势差 {d0:.1f}°")
    N = 16
    idxs = [c0 + int(round(k*(c1-c0)/N)) for k in range(N)]
    print(f"采样帧: {idxs}")
    # 参考根位（让 pelvis 居中、z 原地循环）
    zref = sum(data[i][2] for i in idxs)/N
    xref = sum(data[i][0] for i in idxs)/N
    yref = data[c0][1]  # 首帧骨盆高 → 使支撑脚着地
    rot_tables = {}   # 我们关节 -> {x: [], y: [], z: []} 弧度
    root_x, root_y, root_z = [], [], []
    for fr in idxs:
        ch = frame_channels(root, data[fr])
        for cmu, wej in ROT_MAP.items():
            zr, yr, xr = ch[cmu]['rot']
            d = rot_tables.setdefault(wej, {'x':[], 'y':[], 'z':[]})
            d['x'].append(round(-math.radians(xr), 5))  # 镜像 x
            d['y'].append(round(-math.radians(yr), 5))  # 镜像 y
            d['z'].append(round(math.radians(zr), 5))    # z 同
        p = ch['Hips']['pos']
        root_x.append(round(-(p[0]-xref)*S, 2))
        root_y.append(round((yref-p[1])*S, 2))          # CMU 上→我们下
        root_z.append(0.0)  # 循环走：原地（z 前进位移移除，腿步幅真实）
    # 组装 fk3d.rotations3d
    rotations3d = {}
    for wej, d in rot_tables.items():
        comp = {}
        if len(set(d['x']))>1 or d['x'][0]!=0: comp['x_rot'] = {'table': d['x']}
        if len(set(d['y']))>1 or d['y'][0]!=0: comp['y_rot'] = {'table': d['y']}
        if len(set(d['z']))>1 or d['z'][0]!=0: comp['z_rot'] = {'table': d['z']}
        rotations3d[wej] = comp
    # 生成 walk3d.json（纯 FK，无 IK）
    motion = {
        "schema": "assetslab_motion3d_v1",
        "motion_id": "walk3d",
        "title": "Walk 3D — CMU 真实动捕",
        "description": "骨骼与动作 100% 来自 CMU MoCap subject16 16_15.bvh：全关节每帧真实旋转 + 真实根位移。",
        "species": "human",
        "frame_count": N,
        "signals": {},
        "params": {},
        "fk3d": {"root": "pelvis", "rotations3d": rotations3d},
        "root3d": {"x": {"table": root_x}, "y": {"table": root_y}, "z": {"table": root_z}},
    }
    p = WE/'assetslab/species/human/actions3d/walk3d.json'
    p.write_text(json.dumps(motion, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print("\n已写 walk3d.json (真实 CMU 旋转)")
    # 验证：用我们引擎 FK vs CMU 真实坐标
    from assetslab.skeleton3d import build_skeleton_3d, pose_3d
    sk = build_skeleton_3d('human')
    m = json.loads(p.read_text(encoding='utf-8'))
    print("\n验证 (我们 FK vs CMU 真实, 误差px):")
    for k in range(N):
        pose = pose_3d(sk, m, k)
        cmu = fk_world(root, data[idxs[k]])
        def to_we(j):
            x,y,z = cmu[j]
            return [CENTER_X - x*S, pelvis_we - (y + (yref - 0.0))*S + (yref - 0.0)*S, z*S]
        # 简化：用 CMU Hips 位移对齐
        hx = CENTER_X - (cmu['Hips'][0]-xref)*S
        hy = pelvis_we - (yref - cmu['Hips'][1])*S
        hz = (cmu['Hips'][2]-zref)*S
        def cmu_we(j):
            x,y,z = cmu[j]
            dx, dy, dz = x-cmu['Hips'][0], y-cmu['Hips'][1], z-cmu['Hips'][2]
            return [hx - dx*S, hy - dy*S, hz + dz*S]
        # 对比几个关键关节
        errs = []
        for wej, cmuj in [('hip_left','LeftUpLeg'),('knee_left','LeftLeg'),('ankle_left','LeftFoot'),
                          ('toe_left','LeftToeBase'),('shoulder_left','LeftArm'),('elbow_left','LeftForeArm'),
                          ('wrist_left','LeftHand'),('head','Head'),('chest','Spine1')]:
            a = pose[wej]; b = cmu_we(cmuj)
            errs.append((wej, math.dist(a,b)))
        worst = max(errs, key=lambda t:t[1])
        print(f"  f{k}: 最大误差 {worst[1]:5.1f}px @{worst[0]}")
    # 脚着地检查
    print("\n脚 y (目标≈470 着地):")
    for k in range(N):
        pose = pose_3d(sk, m, k)
        print(f"  f{k}: 左脚趾 {pose['toe_left'][1]:6.1f} 右脚趾 {pose['toe_right'][1]:6.1f}")

if __name__ == '__main__':
    root, nf, ft, data = load_cmu()
    if '--inspect' in sys.argv:
        print(f"== CMU {BVH.name}: {nf} 帧, {ft}s/帧, {count(root)} 关节 ==")
        print("\n== 骨长（相对父 OFFSET）==")
        for name,(L,off) in bone_lengths(root).items():
            print(f"  {name:16s} 长 {L:7.3f}  dir {[round(v,3) for v in off]}")
        xs=[float(d[0]) for d in data]; ys=[float(d[1]) for d in data]; zs=[float(d[2]) for d in data]
        print(f"\n根 Hips: x [{min(xs):.2f},{max(xs):.2f}] y [{min(ys):.2f},{max(ys):.2f}] z [{min(zs):.2f},{max(zs):.2f}]")
        feet_y = [min([fk_world(root,f)[n][1] for n in ('LeftToeBase','RightToeBase','LeftFoot','RightFoot')]) for f in data]
        print(f"脚底(CMU 世界 y, 向上): [{min(feet_y):.2f}, {max(feet_y):.2f}]")
        print("\n== 关节旋转范围(度) ==")
        jidx = {j.name: n for n,j in enumerate(flatten(root))}
        print(f"{'关节':16s} {'Z':>14s} {'Y':>14s} {'X':>14s}")
        for nm in NAMES:
            i = jidx[nm]-1
            Z=[d[6+3*i+0] for d in data]; Y=[d[6+3*i+1] for d in data]; X=[d[6+3*i+2] for d in data]
            print(f"{nm:16s} [{min(Z):6.1f},{max(Z):6.1f}] [{min(Y):6.1f},{max(Y):6.1f}] [{min(X):6.1f},{max(X):6.1f}]")
    elif '--skeleton' in sys.argv:
        write_skeleton()
    elif '--walk' in sys.argv:
        write_walk()
    else:
        print("用法: rebuild_skeleton_cmu.py --inspect | --skeleton | --walk")
