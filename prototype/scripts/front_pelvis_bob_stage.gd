extends Node2D

const FRONT_BASE := preload("res://scripts/front_skeleton_stage.gd")
const LEG_STAGE := preload("res://scripts/front_leg_cycle_stage.gd")
const FRAME_COUNT := 8
const CENTER_X := 480.0
const FLOOR_Y := 470.0
const STATIC_COLOR := Color("5f7c9f")
const REAR_LEG_COLOR := Color("7f9fc4")
const FRONT_LEG_COLOR := Color("ffd27a")
const JOINT_COLOR := Color("f4f7ff")
const PELVIS_COLOR := Color("ffbc73")
const PELVIS_OFFSETS := [-2.0, -1.0, 1.0, 3.0, -2.0, -1.0, 1.0, 3.0]

var frame_index := 0:
	set(value):
		frame_index = posmod(value, FRAME_COUNT)
		queue_redraw()


func front_base_points() -> Dictionary:
	return FRONT_BASE.new().front_base_points()


func pelvis_offset(index: int) -> float:
	return PELVIS_OFFSETS[posmod(index, FRAME_COUNT)]


func leg_pose(index: int) -> Dictionary:
	var accepted_pose := LEG_STAGE.new().leg_pose(index)
	var offset := Vector2(0.0, pelvis_offset(index))
	accepted_pose["pelvis"] = front_base_points()["pelvis"] + offset
	accepted_pose["left_hip"] += offset
	accepted_pose["right_hip"] += offset
	# The knees follow only half of the pelvis displacement. Feet deliberately
	# remain byte-for-byte equivalent to stage 2 so the shared floor contact is
	# still the source of truth for the next stage.
	accepted_pose["left_knee"] += offset * 0.5
	accepted_pose["right_knee"] += offset * 0.5
	return accepted_pose


func validate_pelvis_bob() -> PackedStringArray:
	var errors := PackedStringArray()
	var accepted_model := LEG_STAGE.new()
	var base := front_base_points()
	var minimum_offset := INF
	var maximum_offset := -INF
	for index in range(FRAME_COUNT):
		var pose := leg_pose(index)
		var accepted_pose := accepted_model.leg_pose(index)
		var offset := pelvis_offset(index)
		minimum_offset = minf(minimum_offset, offset)
		maximum_offset = maxf(maximum_offset, offset)
		if not is_equal_approx(pose["pelvis"].x, CENTER_X):
			errors.append("frame %d shifts the pelvis off the center axis" % index)
		if pose["pelvis"] != base["pelvis"] + Vector2(0.0, offset):
			errors.append("frame %d uses an unexpected pelvis offset" % index)
		if pose["left_hip"] != accepted_pose["left_hip"] + Vector2(0.0, offset) or pose["right_hip"] != accepted_pose["right_hip"] + Vector2(0.0, offset):
			errors.append("frame %d does not carry both hips with the pelvis" % index)
		if pose["left_foot"] != accepted_pose["left_foot"] or pose["right_foot"] != accepted_pose["right_foot"]:
			errors.append("frame %d changes an accepted stage-2 foot position" % index)
		if pose["front_leg"] != accepted_pose["front_leg"]:
			errors.append("frame %d changes the accepted front-leg order" % index)
		if pose["left_foot"].y > FLOOR_Y or pose["right_foot"].y > FLOOR_Y:
			errors.append("frame %d puts a foot below the baseline" % index)
		if not is_equal_approx(pose["left_foot"].y, FLOOR_Y) and not is_equal_approx(pose["right_foot"].y, FLOOR_Y):
			errors.append("frame %d has no planted foot" % index)
	if minimum_offset >= 0.0 or maximum_offset <= 0.0:
		errors.append("pelvis motion must include both upward and downward movement")
	if maximum_offset - minimum_offset > 6.0:
		errors.append("pelvis bob exceeds the 6px stage-3 limit")
	return errors


func _draw() -> void:
	var base := front_base_points()
	var pose := leg_pose(frame_index)
	draw_rect(Rect2(Vector2.ZERO, Vector2(960.0, 600.0)), Color("111827"))
	draw_line(Vector2(160.0, FLOOR_Y), Vector2(800.0, FLOOR_Y), Color("4b5e7a"), 2.0)
	draw_dashed_line(Vector2(CENTER_X, 70.0), Vector2(CENTER_X, 510.0), Color("4b5e7a"), 1.0, 8.0)

	_draw_static_bone(base["head"], base["neck"])
	_draw_static_bone(base["shoulder_left"], base["shoulder_right"])
	_draw_static_bone(base["shoulder_left"], base["elbow_left"])
	_draw_static_bone(base["elbow_left"], base["hand_left"])
	_draw_static_bone(base["shoulder_right"], base["elbow_right"])
	_draw_static_bone(base["elbow_right"], base["hand_right"])
	_draw_static_bone(base["neck"], pose["pelvis"])
	draw_arc(base["head"], 68.0, 0.0, TAU, 48, STATIC_COLOR, 4.0, true)

	var rear_name: String = "right" if pose["front_leg"] == "left" else "left"
	_draw_leg(pose, rear_name, REAR_LEG_COLOR)
	_draw_leg(pose, pose["front_leg"], FRONT_LEG_COLOR)
	draw_circle(pose["pelvis"], 14.0, PELVIS_COLOR)
	for key in ["neck", "shoulder_left", "shoulder_right", "elbow_left", "elbow_right", "hand_left", "hand_right"]:
		draw_circle(base[key], 7.0, JOINT_COLOR)
	for key in ["pelvis", "left_hip", "right_hip", "left_knee", "right_knee", "left_foot", "right_foot"]:
		draw_circle(pose[key], 7.0, JOINT_COLOR)


func _draw_static_bone(from: Vector2, to: Vector2) -> void:
	draw_line(from, to, Color("1d334d"), 12.0, true)
	draw_line(from, to, STATIC_COLOR, 6.0, true)


func _draw_leg(pose: Dictionary, leg_name: String, color: Color) -> void:
	var hip: Vector2 = pose[leg_name + "_hip"]
	var knee: Vector2 = pose[leg_name + "_knee"]
	var foot: Vector2 = pose[leg_name + "_foot"]
	draw_line(hip, knee, Color("1d334d"), 14.0, true)
	draw_line(knee, foot, Color("1d334d"), 14.0, true)
	draw_line(hip, knee, color, 8.0, true)
	draw_line(knee, foot, color, 8.0, true)
	draw_circle(hip, 8.0, color)
	draw_circle(knee, 8.0, color)
	draw_circle(foot, 8.0, color)
