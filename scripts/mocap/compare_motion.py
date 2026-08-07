#!/usr/bin/env python3
"""真实 BVH vs 我们动作：髋/膝屈伸角逐帧比对（统一"绕x屈伸角"，伸直=0，前摆/屈膝为正）。"""
import math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'scripts/mocap'))
from bvh_parser import load_bvh, fk_positions
from assetslab.skeleton3d import build_skeleton_3d, pose_3d

def limb_angle_yz(origin, tip, y_down_sign):
    """肢体(origin->tip)相对垂直向下的前后角（rad），前(z+)为正。y_down_sign: 我们=+1(ydown), CMU=-1(yup)。"""
    dy = (tip[1]-origin[1]) * y_down_sign
    dz = tip[2]-origin[2]
    return math.atan2(dz, dy)

def resample(vals, target):
    n=len(vals); out=[]
    for i in range(target):
        f=i*(n-1)/(target-1) if target>1 else 0
        i0,i1=int(f),min(int(f)+1,n-1); fr=f-i0
        out.append(vals[i0]*(1-fr)+vals[i1]*fr)
    return out

def real_walk_cycle(path, target=8):
    """真实 walk 一个步态周期（左腿 支撑→摆动），重采样到 target 帧。"""
    root,nf,ft,data = load_bvh(path)
    poses=[fk_positions(root,fr) for fr in data]
    # 左脚着地帧 = LeftFoot y 局部最小；取中段
    fy=[p['LeftFoot'][1] for p in poses]
    # 找着地帧序列（左脚 y 低谷）
    mins=[]
    for i in range(2,nf-2):
        if fy[i]<fy[i-1] and fy[i]<fy[i+1] and fy[i]<fy[i+2]:
            mins.append(i)
    if len(mins)<2: seg=poses[len(poses)//3:2*len(poses)//3]
    else:
        a,b=mins[len(mins)//2], mins[len(mins)//2+1]
        seg=poses[a:b]
    hip_l=[math.degrees(limb_angle_yz(p['LHipJoint'],p['LeftUpLeg'],-1)) for p in seg]
    knee_l=[math.degrees(limb_angle_yz(p['LeftUpLeg'],p['LeftLeg'],-1)-limb_angle_yz(p['LeftLeg'],p['LeftFoot'],-1)) for p in seg]
    sh_l=[math.degrees(limb_angle_yz(p['LeftShoulder'],p['LeftArm'],-1)) for p in seg]
    el_l=[math.degrees(math.acos(max(-1,min(1,
        sum((p['LeftForeArm'][i]-p['LeftArm'][i])*(p['LeftHand'][i]-p['LeftForeArm'][i]) for i in range(3))
        /( (math.dist(p['LeftArm'],p['LeftForeArm'])*math.dist(p['LeftForeArm'],p['LeftHand'])) or 1e-9) )))) for p in seg]
    return resample(hip_l,target), resample(knee_l,target), resample(sh_l,target), resample(el_l,target)

def our_walk_angles():
    sk=build_skeleton_3d('human')
    import json
    m=json.load(open(str(ROOT/'assetslab/species/human/actions3d/walk3d.json')))
    hip=[];knee=[];sh=[];el=[]
    for i in range(8):
        p=pose_3d(sk,m,i)
        hip.append(math.degrees(limb_angle_yz(p['hip_left'],p['knee_left'],1)))
        knee.append(math.degrees(limb_angle_yz(p['hip_left'],p['knee_left'],1)-limb_angle_yz(p['knee_left'],p['ankle_left'],1)))
        sh.append(math.degrees(limb_angle_yz(p['shoulder_left'],p['elbow_left'],1)))
        a=math.dist(p['shoulder_left'],p['elbow_left']); b=math.dist(p['elbow_left'],p['wrist_left']); c=math.dist(p['shoulder_left'],p['wrist_left'])
        el.append(math.degrees(math.acos(max(-1,min(1,(a*a+b*b-c*c)/(2*a*b))))))
    return hip,knee,sh,el

if __name__=='__main__':
    rh,rk,rs,re_ = real_walk_cycle('/tmp/16_15.bvh')
    oh,ok,os_,oe = our_walk_angles()
    print('帧 | 髋 真实/我们 | 膝 真实/我们 | 肩 真实/我们 | 肘角 真实/我们')
    for i in range(8):
        print(f'f{i} | {rh[i]:+5.1f}/{oh[i]:+5.1f}° | {rk[i]:+5.1f}/{ok[i]:+5.1f}° | {rs[i]:+6.1f}/{os_[i]:+5.1f}° | {re_[i]:.0f}/{oe[i]:.0f}°')
    def rng(v): return max(v)-min(v)
    print(f'\n幅度: 髋 真{rng(rh):.1f}/我{rng(oh):.1f}°  膝 真{rng(rk):.1f}/我{rng(ok):.1f}°  肩 真{rng(rs):.1f}/我{rng(os_):.1f}°')
