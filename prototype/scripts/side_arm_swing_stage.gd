extends Node2D

const SIDE_BASE := preload("res://scripts/side_skeleton_stage.gd")
const PELVIS_STAGE := preload("res://scripts/side_pelvis_bob_stage.gd")
const FRAME_COUNT := 8
const ROOT_X := 480.0
const FLOOR_Y := 470.0
const STATIC_COLOR := Color("5f7c9f")
const REAR_COLOR := Color("7f9fc4")
const FRONT_COLOR := Color("ffd27a")
const ARM_COLOR := Color("a9e8c3")
const JOINT_COLOR := Color("f4f7ff")

var frame_index := 0:
	set(value): frame_index = posmod(value, FRAME_COUNT); queue_redraw()

func side_base_points() -> Dictionary: return SIDE_BASE.new().side_base_points()
func walk_pose(index: int) -> Dictionary: return PELVIS_STAGE.new().walk_pose(index)

func arm_pose(index: int) -> Dictionary:
	var base := side_base_points()
	var stride := cos(TAU * float(posmod(index, FRAME_COUNT)) / float(FRAME_COUNT))
	var rear_offset := Vector2(7.0 * stride, 3.0 * stride)
	var front_offset := -rear_offset
	return {"rear_elbow": base["rear_elbow"] + rear_offset, "rear_hand": base["rear_hand"] + rear_offset * 2.0, "front_elbow": base["front_elbow"] + front_offset, "front_hand": base["front_hand"] + front_offset * 2.0}

func validate_side_arm_swing() -> PackedStringArray:
	var errors := PackedStringArray()
	var accepted := PELVIS_STAGE.new()
	var base := side_base_points()
	for index in range(FRAME_COUNT):
		var pose := walk_pose(index)
		var old := accepted.walk_pose(index)
		var arms := arm_pose(index)
		for key in ["pelvis", "rear_hip", "front_hip", "rear_knee", "front_knee", "rear_foot", "front_foot", "foreground_leg"]:
			if pose[key] != old[key]: errors.append("frame %d changes accepted side-pelvis key %s" % [index, key])
		if not (arms["rear_hand"] - base["rear_hand"]).is_equal_approx(-(arms["front_hand"] - base["front_hand"])): errors.append("frame %d hands are not opposite" % index)
		if arms["rear_hand"].y <= base["rear_shoulder"].y or arms["front_hand"].y <= base["front_shoulder"].y: errors.append("frame %d lifts hand above shoulder" % index)
		if (arms["front_hand"].x - base["front_hand"].x) * (pose["front_foot"].x - (ROOT_X + 2.0)) > 0.01: errors.append("frame %d front arm is not counterphased to front leg" % index)
	if arm_pose(0)["front_hand"].x >= base["front_hand"].x or arm_pose(4)["front_hand"].x <= base["front_hand"].x: errors.append("front arm does not complete its side swing")
	return errors

func _draw() -> void:
	var base := side_base_points(); var pose := walk_pose(frame_index); var arms := arm_pose(frame_index)
	draw_rect(Rect2(Vector2.ZERO, Vector2(960, 600)), Color("111827")); draw_line(Vector2(160,FLOOR_Y),Vector2(800,FLOOR_Y),Color("4b5e7a"),2.0); draw_dashed_line(Vector2(ROOT_X,70),Vector2(ROOT_X,510),Color("4b5e7a"),1.0,8.0)
	draw_string(ThemeDB.fallback_font,Vector2(710,100),"FACING RIGHT",HORIZONTAL_ALIGNMENT_LEFT,-1,20,ARM_COLOR); draw_line(base["head"],base["face_forward"],ARM_COLOR,3.0,true); draw_colored_polygon(PackedVector2Array([Vector2(548,150),Vector2(534,142),Vector2(534,158)]),ARM_COLOR)
	_bone(base["head"],base["neck"],STATIC_COLOR,7); _bone(base["neck"],pose["pelvis"],STATIC_COLOR,7); draw_arc(base["head"],68,0,TAU,48,STATIC_COLOR,4,true)
	_bone(base["rear_shoulder"],arms["rear_elbow"],ARM_COLOR,7); _bone(arms["rear_elbow"],arms["rear_hand"],ARM_COLOR,7); _bone(base["front_shoulder"],arms["front_elbow"],ARM_COLOR,7); _bone(arms["front_elbow"],arms["front_hand"],ARM_COLOR,7)
	var rear_name: String = "front" if pose["foreground_leg"] == "rear" else "rear"; _leg(pose,rear_name,REAR_COLOR if rear_name=="rear" else FRONT_COLOR); _leg(pose,pose["foreground_leg"],FRONT_COLOR if pose["foreground_leg"]=="front" else REAR_COLOR)
	draw_circle(pose["pelvis"],14,Color("ffbc73"))
	for key in ["neck","rear_shoulder","front_shoulder"]: draw_circle(base[key],7,JOINT_COLOR)
	for key in ["rear_elbow","rear_hand","front_elbow","front_hand"]: draw_circle(arms[key],7,JOINT_COLOR)
	for key in ["pelvis","rear_hip","front_hip","rear_knee","front_knee","rear_foot","front_foot"]: draw_circle(pose[key],7,JOINT_COLOR)

func _bone(from: Vector2,to: Vector2,color: Color,width: float) -> void: draw_line(from,to,Color("1d334d"),width+6,true); draw_line(from,to,color,width,true)
func _leg(pose: Dictionary,limb: String,color: Color) -> void: _bone(pose[limb+"_hip"],pose[limb+"_knee"],color,8); _bone(pose[limb+"_knee"],pose[limb+"_foot"],color,8)
