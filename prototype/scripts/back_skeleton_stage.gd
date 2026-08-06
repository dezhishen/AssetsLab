extends Node2D

const CENTER_X := 480.0
const FLOOR_Y := 470.0
const BONE_COLOR := Color("9dd6ff")
const REAR_COLOR := Color("7f9fc4")
const FRONT_COLOR := Color("ffd27a")
const JOINT_COLOR := Color("fff1a8")
const GUIDE_COLOR := Color("4b5e7a")

func back_base_points() -> Dictionary:
	return {"head":Vector2(CENTER_X,150),"neck":Vector2(CENTER_X,238),"chest":Vector2(CENTER_X,268),"waist":Vector2(CENTER_X,306),"pelvis":Vector2(CENTER_X,350),"rear_shoulder_left":Vector2(422,264),"rear_shoulder_right":Vector2(538,264),"front_shoulder_left":Vector2(432,258),"front_shoulder_right":Vector2(528,258),"rear_elbow_left":Vector2(400,326),"rear_elbow_right":Vector2(560,326),"front_elbow_left":Vector2(410,320),"front_elbow_right":Vector2(550,320),"rear_hand_left":Vector2(392,382),"rear_hand_right":Vector2(568,382),"front_hand_left":Vector2(402,376),"front_hand_right":Vector2(558,376),"rear_hip_left":Vector2(448,356),"rear_hip_right":Vector2(512,356),"front_hip_left":Vector2(456,350),"front_hip_right":Vector2(504,350),"rear_knee_left":Vector2(448,414),"rear_knee_right":Vector2(512,414),"front_knee_left":Vector2(456,410),"front_knee_right":Vector2(504,410),"rear_foot_left":Vector2(448,FLOOR_Y),"rear_foot_right":Vector2(512,FLOOR_Y),"front_foot_left":Vector2(456,FLOOR_Y),"front_foot_right":Vector2(504,FLOOR_Y)}

func validate_back_base() -> PackedStringArray:
	var p:=back_base_points(); var errors:=PackedStringArray()
	if p["head"].x!=CENTER_X or p["neck"].x!=CENTER_X or p["pelvis"].x!=CENTER_X: errors.append("back center anchors are not on the axis")
	for pair in [["rear_shoulder_left","rear_shoulder_right"],["front_shoulder_left","front_shoulder_right"],["rear_hip_left","rear_hip_right"],["front_hip_left","front_hip_right"],["rear_foot_left","rear_foot_right"],["front_foot_left","front_foot_right"]]:
		if not is_equal_approx(CENTER_X-p[pair[0]].x,p[pair[1]].x-CENTER_X): errors.append("back pair %s is not symmetric"%pair[0])
	for limb in ["rear","front"]:
		for side in ["left","right"]:
			if p[limb+"_knee_"+side].y<=p[limb+"_hip_"+side].y: errors.append("%s %s knee is not below hip"%[limb,side])
			if p[limb+"_foot_"+side].y!=FLOOR_Y: errors.append("%s %s foot misses baseline"%[limb,side])
	return errors

func _draw() -> void:
	var p:=back_base_points(); draw_rect(Rect2(Vector2.ZERO,Vector2(960,600)),Color("111827")); draw_line(Vector2(160,FLOOR_Y),Vector2(800,FLOOR_Y),GUIDE_COLOR,2); draw_dashed_line(Vector2(CENTER_X,70),Vector2(CENTER_X,510),GUIDE_COLOR,1,8); draw_string(ThemeDB.fallback_font,Vector2(710,100),"BACK VIEW",HORIZONTAL_ALIGNMENT_LEFT,-1,20,Color("d8b4fe"))
	_bone(p["head"],p["neck"],BONE_COLOR,7); _bone(p["neck"],p["chest"],BONE_COLOR,7); _bone(p["chest"],p["waist"],BONE_COLOR,7); _bone(p["waist"],p["pelvis"],BONE_COLOR,7); draw_arc(p["head"],68,0,TAU,48,BONE_COLOR,4,true)
	for limb in ["rear","front"]:
		var color:=REAR_COLOR if limb=="rear" else FRONT_COLOR
		for side in ["left","right"]:
			_bone(p[limb+"_shoulder_"+side],p[limb+"_elbow_"+side],color,7); _bone(p[limb+"_elbow_"+side],p[limb+"_hand_"+side],color,7); _bone(p["pelvis"],p[limb+"_hip_"+side],color,7); _bone(p[limb+"_hip_"+side],p[limb+"_knee_"+side],color,7); _bone(p[limb+"_knee_"+side],p[limb+"_foot_"+side],color,7)
	draw_circle(p["pelvis"],14,Color("ffbc73")); for key in p: draw_circle(p[key],7,JOINT_COLOR)
func _bone(from:Vector2,to:Vector2,color:Color,width:float)->void: draw_line(from,to,Color("1d334d"),width+6,true); draw_line(from,to,color,width,true)
