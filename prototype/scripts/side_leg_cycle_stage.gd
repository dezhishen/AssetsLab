extends Node2D

const SIDE_BASE := preload("res://scripts/side_skeleton_stage.gd")
const FRAME_COUNT := 8
const ROOT_X := 480.0
const FLOOR_Y := 470.0
const STATIC_COLOR := Color("5f7c9f")
const REAR_COLOR := Color("7f9fc4")
const FRONT_COLOR := Color("ffd27a")
const JOINT_COLOR := Color("f4f7ff")

var frame_index := 0:
	set(value):
		frame_index = posmod(value, FRAME_COUNT)
		queue_redraw()


func side_base_points() -> Dictionary:
	return SIDE_BASE.new().side_base_points()


func _lift_amount(index: int, leg_name: String) -> float:
	var local_index := posmod(index, FRAME_COUNT)
	if leg_name == "rear" and local_index in [1, 2, 3]:
		return sin(PI * float(local_index) / 4.0)
	if leg_name == "front" and local_index in [5, 6, 7]:
		return sin(PI * float(local_index - 4) / 4.0)
	return 0.0


func leg_pose(index: int) -> Dictionary:
	var base := side_base_points()
	var phase := TAU * float(posmod(index, FRAME_COUNT)) / float(FRAME_COUNT)
	var stride := cos(phase)
	var rear_lift := _lift_amount(index, "rear")
	var front_lift := _lift_amount(index, "front")
	return {
		"rear_hip": base["rear_hip"],
		"front_hip": base["front_hip"],
		"rear_knee": Vector2(ROOT_X - 18.0 * stride, 414.0 - rear_lift * 20.0),
		"front_knee": Vector2(ROOT_X + 18.0 * stride, 410.0 - front_lift * 20.0),
		"rear_foot": Vector2(ROOT_X + 2.0 - 30.0 * stride, FLOOR_Y - rear_lift * 30.0),
		"front_foot": Vector2(ROOT_X + 2.0 + 30.0 * stride, FLOOR_Y - front_lift * 30.0),
		"foreground_leg": "front" if index == 0 or index >= 5 else "rear",
	}


func validate_side_leg_cycle() -> PackedStringArray:
	var errors := PackedStringArray()
	var base := side_base_points()
	for index in range(FRAME_COUNT):
		var pose := leg_pose(index)
		if pose["rear_hip"] != base["rear_hip"] or pose["front_hip"] != base["front_hip"]:
			errors.append("frame %d changes the accepted side hip anchors" % index)
		if pose["rear_foot"].y > FLOOR_Y or pose["front_foot"].y > FLOOR_Y:
			errors.append("frame %d puts a foot below the baseline" % index)
		if not is_equal_approx(pose["rear_foot"].y, FLOOR_Y) and not is_equal_approx(pose["front_foot"].y, FLOOR_Y):
			errors.append("frame %d has no planted foot" % index)
		if pose["rear_knee"].y <= pose["rear_hip"].y or pose["front_knee"].y <= pose["front_hip"].y:
			errors.append("frame %d places a knee above its hip" % index)
	for index in range(4):
		if leg_pose(index + 1)["rear_foot"].x <= leg_pose(index)["rear_foot"].x:
			errors.append("rear foot does not advance through first half-cycle at frame %d" % index)
		if leg_pose(index + 1)["front_foot"].x >= leg_pose(index)["front_foot"].x:
			errors.append("front foot does not retreat through first half-cycle at frame %d" % index)
	if leg_pose(0)["foreground_leg"] != "front" or leg_pose(4)["foreground_leg"] != "rear":
		errors.append("foreground leg does not change at the opposite contact")
	if not is_equal_approx(leg_pose(2)["rear_foot"].y, FLOOR_Y - 30.0) or not is_equal_approx(leg_pose(6)["front_foot"].y, FLOOR_Y - 30.0):
		errors.append("passing frames do not reach the expected foot lift")
	return errors


func _draw() -> void:
	var base := side_base_points()
	var pose := leg_pose(frame_index)
	draw_rect(Rect2(Vector2.ZERO, Vector2(960.0, 600.0)), Color("111827"))
	draw_line(Vector2(160.0, FLOOR_Y), Vector2(800.0, FLOOR_Y), Color("4b5e7a"), 2.0)
	draw_dashed_line(Vector2(ROOT_X, 70.0), Vector2(ROOT_X, 510.0), Color("4b5e7a"), 1.0, 8.0)
	draw_string(ThemeDB.fallback_font, Vector2(710.0, 100.0), "FACING RIGHT", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 20, Color("a9e8c3"))
	draw_line(base["head"], base["face_forward"], Color("a9e8c3"), 3.0, true)
	draw_colored_polygon(PackedVector2Array([Vector2(548.0, 150.0), Vector2(534.0, 142.0), Vector2(534.0, 158.0)]), Color("a9e8c3"))

	_draw_static_bone(base["head"], base["neck"])
	_draw_static_bone(base["neck"], base["pelvis"])
	_draw_arm(base, "rear", REAR_COLOR)
	_draw_arm(base, "front", FRONT_COLOR)
	draw_arc(base["head"], 68.0, 0.0, TAU, 48, STATIC_COLOR, 4.0, true)

	var rear_name: String = "front" if pose["foreground_leg"] == "rear" else "rear"
	_draw_leg(pose, rear_name, REAR_COLOR if rear_name == "rear" else FRONT_COLOR)
	_draw_leg(pose, pose["foreground_leg"], FRONT_COLOR if pose["foreground_leg"] == "front" else REAR_COLOR)
	draw_circle(base["pelvis"], 14.0, Color("ffbc73"))
	for key in ["neck", "pelvis", "rear_shoulder", "front_shoulder", "rear_elbow", "front_elbow", "rear_hand", "front_hand"]:
		draw_circle(base[key], 7.0, JOINT_COLOR)
	for key in ["rear_hip", "front_hip", "rear_knee", "front_knee", "rear_foot", "front_foot"]:
		draw_circle(pose[key], 7.0, JOINT_COLOR)


func _draw_static_bone(from: Vector2, to: Vector2) -> void:
	draw_line(from, to, Color("1d334d"), 13.0, true)
	draw_line(from, to, STATIC_COLOR, 7.0, true)


func _draw_arm(base: Dictionary, limb: String, color: Color) -> void:
	_draw_colored_bone(base[limb + "_shoulder"], base[limb + "_elbow"], color)
	_draw_colored_bone(base[limb + "_elbow"], base[limb + "_hand"], color)


func _draw_leg(pose: Dictionary, limb: String, color: Color) -> void:
	_draw_colored_bone(pose[limb + "_hip"], pose[limb + "_knee"], color)
	_draw_colored_bone(pose[limb + "_knee"], pose[limb + "_foot"], color)


func _draw_colored_bone(from: Vector2, to: Vector2, color: Color) -> void:
	draw_line(from, to, Color("1d334d"), 14.0, true)
	draw_line(from, to, color, 8.0, true)
