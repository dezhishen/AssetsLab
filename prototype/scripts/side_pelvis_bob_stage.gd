extends Node2D

const SIDE_BASE := preload("res://scripts/side_skeleton_stage.gd")
const LEG_STAGE := preload("res://scripts/side_leg_cycle_stage.gd")
const FRAME_COUNT := 8
const ROOT_X := 480.0
const FLOOR_Y := 470.0
const STATIC_COLOR := Color("5f7c9f")
const REAR_COLOR := Color("7f9fc4")
const FRONT_COLOR := Color("ffd27a")
const JOINT_COLOR := Color("f4f7ff")
const PELVIS_OFFSETS := [-2.0, -1.0, 1.0, 3.0, -2.0, -1.0, 1.0, 3.0]

var frame_index := 0:
	set(value):
		frame_index = posmod(value, FRAME_COUNT)
		queue_redraw()


func side_base_points() -> Dictionary:
	return SIDE_BASE.new().side_base_points()


func pelvis_offset(index: int) -> float:
	return PELVIS_OFFSETS[posmod(index, FRAME_COUNT)]


func walk_pose(index: int) -> Dictionary:
	var accepted_pose := LEG_STAGE.new().leg_pose(index)
	var offset := Vector2(0.0, pelvis_offset(index))
	accepted_pose["pelvis"] = side_base_points()["pelvis"] + offset
	accepted_pose["rear_hip"] += offset
	accepted_pose["front_hip"] += offset
	accepted_pose["rear_knee"] += offset * 0.5
	accepted_pose["front_knee"] += offset * 0.5
	return accepted_pose


func validate_side_pelvis_bob() -> PackedStringArray:
	var errors := PackedStringArray()
	var accepted_model := LEG_STAGE.new()
	var base := side_base_points()
	var minimum_offset := INF
	var maximum_offset := -INF
	for index in range(FRAME_COUNT):
		var pose := walk_pose(index)
		var accepted_pose := accepted_model.leg_pose(index)
		var offset := pelvis_offset(index)
		minimum_offset = minf(minimum_offset, offset)
		maximum_offset = maxf(maximum_offset, offset)
		if pose["pelvis"] != base["pelvis"] + Vector2(0.0, offset) or not is_equal_approx(pose["pelvis"].x, ROOT_X):
			errors.append("frame %d has an invalid side pelvis position" % index)
		for key in ["rear_foot", "front_foot", "foreground_leg"]:
			if pose[key] != accepted_pose[key]:
				errors.append("frame %d changes accepted side-leg key %s" % [index, key])
		if pose["rear_hip"] != accepted_pose["rear_hip"] + Vector2(0.0, offset) or pose["front_hip"] != accepted_pose["front_hip"] + Vector2(0.0, offset):
			errors.append("frame %d does not carry both side hips with pelvis" % index)
		if pose["rear_foot"].y > FLOOR_Y or pose["front_foot"].y > FLOOR_Y:
			errors.append("frame %d puts a foot below the baseline" % index)
		if not is_equal_approx(pose["rear_foot"].y, FLOOR_Y) and not is_equal_approx(pose["front_foot"].y, FLOOR_Y):
			errors.append("frame %d has no planted foot" % index)
	if minimum_offset >= 0.0 or maximum_offset <= 0.0:
		errors.append("side pelvis must travel above and below its base")
	if maximum_offset - minimum_offset > 6.0:
		errors.append("side pelvis bob exceeds the 6px limit")
	return errors


func _draw() -> void:
	var base := side_base_points()
	var pose := walk_pose(frame_index)
	draw_rect(Rect2(Vector2.ZERO, Vector2(960.0, 600.0)), Color("111827"))
	draw_line(Vector2(160.0, FLOOR_Y), Vector2(800.0, FLOOR_Y), Color("4b5e7a"), 2.0)
	draw_dashed_line(Vector2(ROOT_X, 70.0), Vector2(ROOT_X, 510.0), Color("4b5e7a"), 1.0, 8.0)
	draw_string(ThemeDB.fallback_font, Vector2(710.0, 100.0), "FACING RIGHT", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 20, Color("a9e8c3"))
	draw_line(base["head"], base["face_forward"], Color("a9e8c3"), 3.0, true)
	draw_colored_polygon(PackedVector2Array([Vector2(548.0, 150.0), Vector2(534.0, 142.0), Vector2(534.0, 158.0)]), Color("a9e8c3"))

	_draw_static_bone(base["head"], base["neck"])
	_draw_static_bone(base["neck"], pose["pelvis"])
	_draw_arm(base, "rear", REAR_COLOR)
	_draw_arm(base, "front", FRONT_COLOR)
	draw_arc(base["head"], 68.0, 0.0, TAU, 48, STATIC_COLOR, 4.0, true)
	var rear_name: String = "front" if pose["foreground_leg"] == "rear" else "rear"
	_draw_leg(pose, rear_name, REAR_COLOR if rear_name == "rear" else FRONT_COLOR)
	_draw_leg(pose, pose["foreground_leg"], FRONT_COLOR if pose["foreground_leg"] == "front" else REAR_COLOR)
	draw_circle(pose["pelvis"], 14.0, Color("ffbc73"))
	for key in ["neck", "rear_shoulder", "front_shoulder", "rear_elbow", "front_elbow", "rear_hand", "front_hand"]:
		draw_circle(base[key], 7.0, JOINT_COLOR)
	for key in ["pelvis", "rear_hip", "front_hip", "rear_knee", "front_knee", "rear_foot", "front_foot"]:
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
