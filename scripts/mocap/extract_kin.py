#!/usr/bin/env python3
"""从真实 BVH 提取关键运动学（关节角度曲线 + 骨盆运动 + 步态相位）。

角度用关节位置向量计算（不依赖欧拉角解释），侧视 y-z 平面：
- 髋屈伸：大腿(LHipJoint->LeftUpLeg)相对垂直(-y)的前后角，正=前
- 膝屈曲：大腿(LUpLeg->LLeg)与小腿(LLeg->LFoot)夹角
- 肩摆动：上臂(LShoulder->LArm)相对垂直(-y)的前后角
- 骨盆：Hips 的 x(横移) / y(起伏)
"""
import math, sys
sys.path.insert(0, 'scripts/mocap')
from bvh_parser import load_bvh, fk_positions

def angle_vert_yz(p0, p1):
    """向量 p0->p1 相对垂直向下(-y)在 yz 平面的前后角（rad）。正=向前(z+)。"""
    dx = p1[0]-p0[0]; dy = p1[1]-p0[1]; dz = p1[2]-p0[2]
    # 向下参考：-y。投影到 yz 平面
    vy = -dy; vz = dz
    return math.atan2(vz, vy)

def angle_between(p0, p1, p2):
    """p0->p1 与 p1->p2 的夹角（rad）。"""
    a = [p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]]
    b = [p2[0]-p1[0], p2[1]-p1[1], p2[2]-p1[2]]
    la = math.sqrt(sum(v*v for v in a)); lb = math.sqrt(sum(v*v for v in b))
    if la*lb < 1e-9: return 0.0
    cos = sum(a[i]*b[i] for i in range(3))/(la*lb)
    return math.acos(max(-1, min(1, cos)))

def extract(path):
    root, nf, ft, data = load_bvh(path)
    poses = [fk_positions(root, fr) for fr in data]
    kin = []
    for p in poses:
        hip_l = angle_vert_yz(p['LHipJoint'], p['LeftUpLeg'])
        hip_r = angle_vert_yz(p['RHipJoint'], p['RightUpLeg'])
        knee_l = angle_between(p['LeftUpLeg'], p['LeftLeg'], p['LeftFoot'])
        knee_r = angle_between(p['RightUpLeg'], p['RightLeg'], p['RightFoot'])
        sh_l = angle_vert_yz(p['LeftShoulder'], p['LeftArm'])
        sh_r = angle_vert_yz(p['RightShoulder'], p['RightArm'])
        # 肘角
        elbow_l = angle_between(p['LeftArm'], p['LeftForeArm'], p['LeftHand'])
        kin.append({
            'hip_l': hip_l, 'hip_r': hip_r,
            'knee_l': knee_l, 'knee_r': knee_r,
            'sh_l': sh_l, 'sh_r': sh_r, 'elbow_l': elbow_l,
            'pelvis_x': p['Hips'][0], 'pelvis_y': p['Hips'][1], 'pelvis_z': p['Hips'][2],
            'foot_l_y': p['LeftFoot'][1], 'foot_r_y': p['RightFoot'][1],
        })
    return kin, ft

def report(path, label):
    kin, ft = extract(path)
    n = len(kin)
    # 骨盆运动幅度（去均值）
    px = [k['pelvis_x'] for k in kin]; py = [k['pelvis_y'] for k in kin]
    hip_l = [math.degrees(k['hip_l']) for k in kin]
    hip_r = [math.degrees(k['hip_r']) for k in kin]
    knee_l = [math.degrees(k['knee_l']) for k in kin]
    knee_r = [math.degrees(k['knee_r']) for k in kin]
    sh_l = [math.degrees(k['sh_l']) for k in kin]
    elbow_l = [math.degrees(k['elbow_l']) for k in kin]
    print(f'=== {label} ({path.split("/")[-1]}, {n}帧, {ft*1000:.1f}ms/帧) ===')
    print(f'  骨盆横移(x) 幅: {max(px)-min(px):.2f}  起伏(y) 幅: {max(py)-min(py):.2f}')
    print(f'  左髋屈伸: min {min(hip_l):+.1f}° max {max(hip_l):+.1f}° 幅 {max(hip_l)-min(hip_l):.1f}°')
    print(f'  左膝屈曲: min {min(knee_l):.1f}° max {max(knee_l):.1f}°')
    print(f'  左肩摆动: min {min(sh_l):+.1f}° max {max(sh_l):+.1f}° 幅 {max(sh_l)-min(sh_l):.1f}°')
    print(f'  左肘角: min {min(elbow_l):.1f}° max {max(elbow_l):.1f}°')
    # 左右髋相位差（协调）
    print(f'  右髋幅: {max(hip_r)-min(hip_r):.1f}° 右膝幅: {max(knee_r)-min(knee_r):.1f}°')
    return kin

if __name__ == '__main__':
    report('/tmp/16_15.bvh', 'WALK')
    report('/tmp/16_35.bvh', 'RUN')
    report('/tmp/16_01.bvh', 'JUMP')
