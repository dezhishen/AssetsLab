extends Node2D

const ROOT_X := 480.0
const FLOOR_Y := 470.0
const BONE_COLOR := Color("9dd6ff")
const REAR_COLOR := Color("7f9fc4")
const FRONT_COLOR := Color("ffd27a")
const JOINT_COLOR := Color("fff1a8")
const GUIDE_COLOR := Color("4b5e7a")


func side_base_points() -> Dictionary:
	return {
		"head": Vector2(ROOT_X, 150.0),
		"face_forward": Vector2(548.0, 150.0),
		"neck": Vector2(ROOT_X, 238.0),
		"chest": Vector2(ROOT_X, 268.0),
		"waist": Vector2(ROOT_X, 306.0),
		"pelvis": Vector2(ROOT_X, 350.0),
		"rear_shoulder": Vector2(462.0, 264.0),
		"front_shoulder": Vector2(498.0, 258.0),
		"rear_elbow": Vector2(448.0, 326.0),
		"front_elbow": Vector2(510.0, 320.0),
		"rear_hand": Vector2(444.0, 382.0),
		"front_hand": Vector2(518.0, 376.0),
		"rear_hip": Vector2(466.0, 356.0),
		"front_hip": Vector2(494.0, 350.0),
		"rear_knee": Vector2(462.0, 414.0),
		"front_knee": Vector2(498.0, 410.0),
		"rear_foot": Vector2(452.0, FLOOR_Y),
		"front_foot": Vector2(512.0, FLOOR_Y),
	}


func validate_side_base() -> PackedStringArray:
	var points := side_base_points()
	var errors := PackedStringArray()
	if points["head"].x != ROOT_X or points["neck"].x != ROOT_X or points["pelvis"].x != ROOT_X:
		errors.append("side root anchors are not on the registration axis")
	if points["face_forward"].x <= points["head"].x:
		errors.append("side head does not face right")
	if points["front_hip"].x <= points["rear_hip"].x or points["front_shoulder"].x <= points["rear_shoulder"].x:
		errors.append("front limb anchors are not in front of rear limb anchors")
	if points["front_foot"].x <= points["rear_foot"].x:
		errors.append("front foot is not ahead of rear foot")
	if points["rear_foot"].y != FLOOR_Y or points["front_foot"].y != FLOOR_Y:
		errors.append("side feet do not share the baseline")
	for limb in ["rear", "front"]:
		if points[limb + "_knee"].y <= points[limb + "_hip"].y:
			errors.append("%s knee must remain below its hip" % limb)
		if points[limb + "_hand"].y <= points[limb + "_shoulder"].y:
			errors.append("%s hand must remain below its shoulder" % limb)
	return errors


func _draw() -> void:
	var points := side_base_points()
	draw_rect(Rect2(Vector2.ZERO, Vector2(960.0, 600.0)), Color("111827"))
	draw_line(Vector2(160.0, FLOOR_Y), Vector2(800.0, FLOOR_Y), GUIDE_COLOR, 2.0)
	draw_dashed_line(Vector2(ROOT_X, 70.0), Vector2(ROOT_X, 510.0), GUIDE_COLOR, 1.0, 8.0)
	draw_string(ThemeDB.fallback_font, Vector2(710.0, 100.0), "FACING RIGHT", HORIZONTAL_ALIGNMENT_LEFT, -1.0, 20, Color("a9e8c3"))
	draw_line(points["head"], points["face_forward"], Color("a9e8c3"), 3.0, true)
	draw_colored_polygon(PackedVector2Array([Vector2(548.0, 150.0), Vector2(534.0, 142.0), Vector2(534.0, 158.0)]), Color("a9e8c3"))

	_draw_bone(points["head"], points["neck"], BONE_COLOR)
	_draw_bone(points["neck"], points["chest"], BONE_COLOR)
	_draw_bone(points["chest"], points["waist"], BONE_COLOR)
	_draw_bone(points["waist"], points["pelvis"], BONE_COLOR)
	draw_arc(points["head"], 68.0, 0.0, TAU, 48, BONE_COLOR, 4.0, true)
	_draw_limb(points, "rear", REAR_COLOR)
	_draw_limb(points, "front", FRONT_COLOR)
	draw_circle(points["pelvis"], 14.0, Color("ffbc73"))
	for key in points:
		if key == "face_forward":
			continue
		draw_circle(points[key], 7.0, JOINT_COLOR)


func _draw_limb(points: Dictionary, limb: String, color: Color) -> void:
	_draw_bone(points[limb + "_shoulder"], points[limb + "_elbow"], color)
	_draw_bone(points[limb + "_elbow"], points[limb + "_hand"], color)
	_draw_bone(points["pelvis"], points[limb + "_hip"], color)
	_draw_bone(points[limb + "_hip"], points[limb + "_knee"], color)
	_draw_bone(points[limb + "_knee"], points[limb + "_foot"], color)


func _draw_bone(from: Vector2, to: Vector2, color: Color) -> void:
	draw_line(from, to, Color("1d334d"), 13.0, true)
	draw_line(from, to, color, 7.0, true)
