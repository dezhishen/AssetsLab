extends Node2D

const FRONT_BASE := preload("res://scripts/front_skeleton_stage.gd")
const FRAME_COUNT := 8
const CENTER_X := 480.0
const FLOOR_Y := 470.0
const STATIC_COLOR := Color("5f7c9f")
const REAR_LEG_COLOR := Color("7f9fc4")
const FRONT_LEG_COLOR := Color("ffd27a")
const JOINT_COLOR := Color("f4f7ff")

var frame_index := 0:
	set(value):
		frame_index = posmod(value, FRAME_COUNT)
		queue_redraw()


func front_base_points() -> Dictionary:
	return FRONT_BASE.new().front_base_points()


func leg_pose(index: int) -> Dictionary:
	var base := front_base_points()
	var phase := TAU * float(posmod(index, FRAME_COUNT)) / float(FRAME_COUNT)
	var left_swing := sin(phase)
	var right_swing := -left_swing
	return {
		"left_hip": base["hip_left"],
		"right_hip": base["hip_right"],
		"left_knee": Vector2(448.0 + left_swing * 15.0, 415.0 - maxf(0.0, left_swing) * 22.0),
		"right_knee": Vector2(512.0 + right_swing * 15.0, 415.0 - maxf(0.0, right_swing) * 22.0),
		"left_foot": Vector2(448.0 + left_swing * 24.0, FLOOR_Y - maxf(0.0, left_swing) * 26.0),
		"right_foot": Vector2(512.0 + right_swing * 24.0, FLOOR_Y - maxf(0.0, right_swing) * 26.0),
		"front_leg": "left" if index < 4 else "right",
	}


func validate_leg_cycle() -> PackedStringArray:
	var errors := PackedStringArray()
	var base := front_base_points()
	for index in range(FRAME_COUNT):
		var pose := leg_pose(index)
		if pose["left_hip"] != base["hip_left"] or pose["right_hip"] != base["hip_right"]:
			errors.append("frame %d changes the pelvis anchors" % index)
		if pose["left_foot"].y > FLOOR_Y or pose["right_foot"].y > FLOOR_Y:
			errors.append("frame %d puts a foot below the baseline" % index)
		if not is_equal_approx(pose["left_foot"].y, FLOOR_Y) and not is_equal_approx(pose["right_foot"].y, FLOOR_Y):
			errors.append("frame %d has no planted foot" % index)
		if pose["left_knee"].y <= pose["left_hip"].y or pose["right_knee"].y <= pose["right_hip"].y:
			errors.append("frame %d places a knee above its hip" % index)
	if leg_pose(0)["front_leg"] == leg_pose(4)["front_leg"]:
		errors.append("front leg does not alternate at the half-cycle")
	return errors


func _draw() -> void:
	var base := front_base_points()
	var pose := leg_pose(frame_index)
	draw_rect(Rect2(Vector2.ZERO, Vector2(960.0, 600.0)), Color("111827"))
	draw_line(Vector2(160.0, FLOOR_Y), Vector2(800.0, FLOOR_Y), Color("4b5e7a"), 2.0)
	draw_dashed_line(Vector2(CENTER_X, 70.0), Vector2(CENTER_X, 510.0), Color("4b5e7a"), 1.0, 8.0)

	_draw_static_bone(base["head"], base["neck"])
	_draw_static_bone(base["shoulder_left"], base["shoulder_right"])
	_draw_static_bone(base["neck"], base["pelvis"])
	_draw_static_bone(base["shoulder_left"], base["elbow_left"])
	_draw_static_bone(base["elbow_left"], base["hand_left"])
	_draw_static_bone(base["shoulder_right"], base["elbow_right"])
	_draw_static_bone(base["elbow_right"], base["hand_right"])
	draw_arc(base["head"], 68.0, 0.0, TAU, 48, STATIC_COLOR, 4.0, true)
	draw_circle(base["pelvis"], 14.0, Color("ffbc73"))

	var rear_name: String = "right" if pose["front_leg"] == "left" else "left"
	_draw_leg(pose, rear_name, REAR_LEG_COLOR)
	_draw_leg(pose, pose["front_leg"], FRONT_LEG_COLOR)
	for key in ["neck", "shoulder_left", "shoulder_right", "elbow_left", "elbow_right", "hand_left", "hand_right", "pelvis"]:
		draw_circle(base[key], 7.0, JOINT_COLOR)


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
