extends Node2D
const BACK:=preload("res://scripts/back_skeleton_stage.gd")
const N:=8
const FLOOR:=470.0
var frame_index:=0:
	set(v): frame_index=posmod(v,N); queue_redraw()
func base()->Dictionary:return BACK.new().back_base_points()
func pose(i:int)->Dictionary:
	var p:=base();var s:=sin(TAU*float(posmod(i,N))/N);var r:=-s
	return {"left_hip":p["front_hip_left"],"right_hip":p["front_hip_right"],"left_knee":Vector2(456+s*15,410-maxf(0,s)*22),"right_knee":Vector2(504+r*15,410-maxf(0,r)*22),"left_foot":Vector2(456+s*24,FLOOR-maxf(0,s)*26),"right_foot":Vector2(504+r*24,FLOOR-maxf(0,r)*26),"foreground":"left" if i<4 else "right"}
func validate()->PackedStringArray:
	var e:=PackedStringArray();var p:=base()
	for i in range(N):
		var q:=pose(i);if q["left_hip"]!=p["front_hip_left"] or q["right_hip"]!=p["front_hip_right"]:e.append("hip drift %d"%i)
		if q["left_foot"].y>FLOOR or q["right_foot"].y>FLOOR or (not is_equal_approx(q["left_foot"].y,FLOOR) and not is_equal_approx(q["right_foot"].y,FLOOR)):e.append("baseline failure %d"%i)
	if pose(0)["foreground"]==pose(4)["foreground"]:e.append("foreground does not alternate")
	return e
func _draw()->void:
	var p:=base();var q:=pose(frame_index);draw_rect(Rect2(Vector2.ZERO,Vector2(960,600)),Color("111827"));draw_line(Vector2(160,FLOOR),Vector2(800,FLOOR),Color("4b5e7a"),2);draw_dashed_line(Vector2(480,70),Vector2(480,510),Color("4b5e7a"),1,8);draw_string(ThemeDB.fallback_font,Vector2(710,100),"BACK VIEW",HORIZONTAL_ALIGNMENT_LEFT,-1,20,Color("d8b4fe"));_b(p["head"],p["neck"],Color("9dd6ff"),7);_b(p["neck"],p["pelvis"],Color("9dd6ff"),7);draw_arc(p["head"],68,0,TAU,48,Color("9dd6ff"),4,true)
	for side in ["left","right"]:_b(p["rear_shoulder_"+side],p["rear_elbow_"+side],Color("7f9fc4"),7);_b(p["rear_elbow_"+side],p["rear_hand_"+side],Color("7f9fc4"),7)
	var backleg:String="right" if q["foreground"]=="left" else "left";_leg(q,backleg,Color("7f9fc4"));_leg(q,q["foreground"],Color("ffd27a"));draw_circle(p["pelvis"],14,Color("ffbc73"));for k in ["neck","pelvis","rear_shoulder_left","rear_shoulder_right","rear_elbow_left","rear_elbow_right","rear_hand_left","rear_hand_right"]:draw_circle(p[k],7,Color("fff1a8"));for joint_key in ["left_hip","right_hip","left_knee","right_knee","left_foot","right_foot"]:draw_circle(q[joint_key],7,Color("fff1a8"))
func _b(a:Vector2,b:Vector2,c:Color,w:float)->void:draw_line(a,b,Color("1d334d"),w+6,true);draw_line(a,b,c,w,true)
func _leg(q:Dictionary,n:String,c:Color)->void:_b(q[n+"_hip"],q[n+"_knee"],c,8);_b(q[n+"_knee"],q[n+"_foot"],c,8)
