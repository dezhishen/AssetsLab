extends Node2D

const FRONT_BASE := preload("res://scripts/front_skeleton_stage.gd")
const PELVIS_STAGE := preload("res://scripts/front_pelvis_bob_stage.gd")
const FRAME_COUNT := 8
const CENTER_X := 480.0
const FLOOR_Y := 470.0
const STATIC_COLOR := Color("5f7c9f")
const REAR_LEG_COLOR := Color("7f9fc4")
const FRONT_LEG_COLOR := Color("ffd27a")
const JOINT_COLOR := Color("f4f7ff")
const PELVIS_COLOR := Color("ffbc73")
const ARM_COLOR := Color("a9e8c3")

var frame_index := 0:
	set(value):
		frame_index = posmod(value, FRAME_COUNT)
		queue_redraw()


func front_base_points() -> Dictionary:
	return FRONT_BASE.new().front_base_points()


func walk_pose(index: int) -> Dictionary:
	return PELVIS_STAGE.new().leg_pose(index)


func arm_pose(index: int) -> Dictionary:
	var base := front_base_points()
	var phase := TAU * float(posmod(index, FRAME_COUNT)) / float(FRAME_COUNT)
	# Counterphase with the corresponding leg: when the left leg advances, the
	# left arm rises/back-swings while the right arm drops/forward-swings.
	var left_swing := -sin(phase)
	var right_swing := -left_swing
	return {
		"left_elbow": base["elbow_left"] + Vector2(left_swing * 5.0, left_swing * 6.0),
		"left_hand": base["hand_left"] + Vector2(left_swing * 10.0, left_swing * 14.0),
		"right_elbow": base["elbow_right"] + Vector2(right_swing * 5.0, right_swing * 6.0),
		"right_hand": base["hand_right"] + Vector2(right_swing * 10.0, right_swing * 14.0),
	}


func validate_arm_swing() -> PackedStringArray:
	var errors := PackedStringArray()
	var accepted_model := PELVIS_STAGE.new()
	var base := front_base_points()
	var minimum_left_hand_y := INF
	var maximum_left_hand_y := -INF
	for index in range(FRAME_COUNT):
		var pose := walk_pose(index)
		var accepted_pose := accepted_model.leg_pose(index)
		var arms := arm_pose(index)
		for key in ["pelvis", "left_hip", "right_hip", "left_knee", "right_knee", "left_foot", "right_foot", "front_leg"]:
			if pose[key] != accepted_pose[key]:
				errors.append("frame %d changes accepted stage-3 key %s" % [index, key])
		if not (arms["left_hand"] - base["hand_left"]).is_equal_approx(-(arms["right_hand"] - base["hand_right"])):
			errors.append("frame %d does not keep the hands in opposite phase" % index)
		if not (arms["left_elbow"] - base["elbow_left"]).is_equal_approx(-(arms["right_elbow"] - base["elbow_right"])):
			errors.append("frame %d does not keep the elbows in opposite phase" % index)
		if arms["left_hand"].y <= base["shoulder_left"].y or arms["right_hand"].y <= base["shoulder_right"].y:
			errors.append("frame %d lifts a hand above its shoulder" % index)
		if arms["left_hand"].x >= CENTER_X or arms["right_hand"].x <= CENTER_X:
			errors.append("frame %d lets a hand cross the center axis" % index)
		minimum_left_hand_y = minf(minimum_left_hand_y, arms["left_hand"].y)
		maximum_left_hand_y = maxf(maximum_left_hand_y, arms["left_hand"].y)
	if minimum_left_hand_y >= base["hand_left"].y or maximum_left_hand_y <= base["hand_left"].y:
		errors.append("left hand does not complete an up-and-down swing")
	if maximum_left_hand_y - minimum_left_hand_y > 30.0:
		errors.append("arm swing exceeds the 28px hand travel limit")
	return errors


func _draw() -> void:
	var base := front_base_points()
	var pose := walk_pose(frame_index)
	var arms := arm_pose(frame_index)
	draw_rect(Rect2(Vector2.ZERO, Vector2(960.0, 600.0)), Color("111827"))
	draw_line(Vector2(160.0, FLOOR_Y), Vector2(800.0, FLOOR_Y), Color("4b5e7a"), 2.0)
	draw_dashed_line(Vector2(CENTER_X, 70.0), Vector2(CENTER_X, 510.0), Color("4b5e7a"), 1.0, 8.0)

	_draw_static_bone(base["head"], base["neck"])
	_draw_static_bone(base["shoulder_left"], base["shoulder_right"])
	_draw_static_bone(base["neck"], pose["pelvis"])
	_draw_arm(base["shoulder_left"], arms["left_elbow"], arms["left_hand"])
	_draw_arm(base["shoulder_right"], arms["right_elbow"], arms["right_hand"])
	draw_arc(base["head"], 68.0, 0.0, TAU, 48, STATIC_COLOR, 4.0, true)

	var rear_name: String = "right" if pose["front_leg"] == "left" else "left"
	_draw_leg(pose, rear_name, REAR_LEG_COLOR)
	_draw_leg(pose, pose["front_leg"], FRONT_LEG_COLOR)
	draw_circle(pose["pelvis"], 14.0, PELVIS_COLOR)
	for key in ["neck", "shoulder_left", "shoulder_right"]:
		draw_circle(base[key], 7.0, JOINT_COLOR)
	for key in ["left_elbow", "left_hand", "right_elbow", "right_hand"]:
		draw_circle(arms[key], 7.0, JOINT_COLOR)
	for key in ["pelvis", "left_hip", "right_hip", "left_knee", "right_knee", "left_foot", "right_foot"]:
		draw_circle(pose[key], 7.0, JOINT_COLOR)


func _draw_static_bone(from: Vector2, to: Vector2) -> void:
	draw_line(from, to, Color("1d334d"), 12.0, true)
	draw_line(from, to, STATIC_COLOR, 6.0, true)


func _draw_arm(shoulder: Vector2, elbow: Vector2, hand: Vector2) -> void:
	draw_line(shoulder, elbow, Color("173b36"), 12.0, true)
	draw_line(elbow, hand, Color("173b36"), 12.0, true)
	draw_line(shoulder, elbow, ARM_COLOR, 6.0, true)
	draw_line(elbow, hand, ARM_COLOR, 6.0, true)


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
