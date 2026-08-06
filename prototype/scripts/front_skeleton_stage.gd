extends Node2D

const CENTER_X := 480.0
const FLOOR_Y := 470.0
const BONE_COLOR := Color("9dd6ff")
const JOINT_COLOR := Color("fff1a8")
const GUIDE_COLOR := Color("4b5e7a")


func front_base_points() -> Dictionary:
	return {
		"head": Vector2(CENTER_X, 150.0),
		"neck": Vector2(CENTER_X, 238.0),
		"chest": Vector2(CENTER_X, 268.0),
		"waist": Vector2(CENTER_X, 306.0),
		"shoulder_left": Vector2(422.0, 260.0),
		"shoulder_right": Vector2(538.0, 260.0),
		"elbow_left": Vector2(400.0, 325.0),
		"elbow_right": Vector2(560.0, 325.0),
		"hand_left": Vector2(392.0, 382.0),
		"hand_right": Vector2(568.0, 382.0),
		"pelvis": Vector2(CENTER_X, 350.0),
		"hip_left": Vector2(448.0, 356.0),
		"hip_right": Vector2(512.0, 356.0),
		"knee_left": Vector2(448.0, 415.0),
		"knee_right": Vector2(512.0, 415.0),
		"foot_left": Vector2(448.0, FLOOR_Y),
		"foot_right": Vector2(512.0, FLOOR_Y),
	}


func validate_front_base() -> PackedStringArray:
	var points := front_base_points()
	var errors := PackedStringArray()
	if points["head"].x != CENTER_X or points["neck"].x != CENTER_X or points["pelvis"].x != CENTER_X:
		errors.append("center anchors are not on the front-view axis")
	if not is_equal_approx(CENTER_X - points["hip_left"].x, points["hip_right"].x - CENTER_X):
		errors.append("hip pair is not symmetric")
	if not is_equal_approx(CENTER_X - points["shoulder_left"].x, points["shoulder_right"].x - CENTER_X):
		errors.append("shoulder pair is not symmetric")
	if points["foot_left"].y != FLOOR_Y or points["foot_right"].y != FLOOR_Y:
		errors.append("front feet do not share the baseline")
	if points["knee_left"].y <= points["hip_left"].y or points["knee_right"].y <= points["hip_right"].y:
		errors.append("knees must remain below hips")
	return errors


func _draw() -> void:
	var points := front_base_points()
	draw_rect(Rect2(Vector2.ZERO, Vector2(960.0, 600.0)), Color("111827"))
	draw_line(Vector2(160.0, FLOOR_Y), Vector2(800.0, FLOOR_Y), GUIDE_COLOR, 2.0)
	draw_dashed_line(Vector2(CENTER_X, 70.0), Vector2(CENTER_X, 510.0), GUIDE_COLOR, 1.0, 8.0)

	_draw_bone(points["head"], points["neck"])
	_draw_bone(points["shoulder_left"], points["shoulder_right"])
	_draw_bone(points["neck"], points["chest"])
	_draw_bone(points["chest"], points["waist"])
	_draw_bone(points["waist"], points["pelvis"])
	_draw_bone(points["shoulder_left"], points["elbow_left"])
	_draw_bone(points["elbow_left"], points["hand_left"])
	_draw_bone(points["shoulder_right"], points["elbow_right"])
	_draw_bone(points["elbow_right"], points["hand_right"])
	_draw_bone(points["hip_left"], points["hip_right"])
	_draw_bone(points["pelvis"], points["hip_left"])
	_draw_bone(points["pelvis"], points["hip_right"])
	_draw_bone(points["hip_left"], points["knee_left"])
	_draw_bone(points["knee_left"], points["foot_left"])
	_draw_bone(points["hip_right"], points["knee_right"])
	_draw_bone(points["knee_right"], points["foot_right"])

	draw_arc(points["head"], 68.0, 0.0, TAU, 48, BONE_COLOR, 4.0, true)
	for point in points.values():
		draw_circle(point, 8.0, JOINT_COLOR)
		draw_arc(point, 8.0, 0.0, TAU, 16, Color("23334a"), 2.0, true)
	draw_circle(points["pelvis"], 14.0, Color("ffbc73"))
	draw_arc(points["pelvis"], 14.0, 0.0, TAU, 20, Color("4d2b20"), 2.0, true)


func _draw_bone(from: Vector2, to: Vector2) -> void:
	draw_line(from, to, Color("1e3a5f"), 13.0, true)
	draw_line(from, to, BONE_COLOR, 7.0, true)
