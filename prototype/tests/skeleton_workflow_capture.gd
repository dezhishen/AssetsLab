extends SceneTree

const ROOT_DIR := "res://assets/characters/generated/skeleton_workflows/"
const CUTOUT_DIR := ROOT_DIR + "cutouts/"
const OUTPUT_ROOT := "res://test_output/skeleton_workflows/"
const FRAME_COUNT := 8

var workflow_name := "A_both_legs_pass"
var workflow: Dictionary
var manifest: Dictionary
var rig_root: Node2D
var skeleton: Skeleton2D
var bones: Dictionary = {}
var limb_sprites: Dictionary = {}
var core_sprite: Sprite2D


func _init() -> void:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--workflow="):
			workflow_name = argument.trim_prefix("--workflow=")
	call_deferred("_run")


func _run() -> void:
	if workflow_name not in ["A_both_legs_pass", "B_front_leg_only_pass"]:
		_fail("unknown workflow: " + workflow_name)
		return
	workflow = _read_json(ROOT_DIR + workflow_name + ".json")
	manifest = _read_json(CUTOUT_DIR + "cutouts_manifest.json")
	_clear_output()
	_build_rig()
	for frame in range(FRAME_COUNT):
		_apply_pose(frame)
		await process_frame
		await process_frame
		_capture_frame(frame)
	print("SKELETON_WORKFLOW_CAPTURE_PASS workflow=%s frames=%d" % [workflow_name, FRAME_COUNT])
	quit(0)


func _read_json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		_fail("could not open " + path)
		return {}
	var value = JSON.parse_string(file.get_as_text())
	if not value is Dictionary:
		_fail("invalid JSON " + path)
		return {}
	return value


func _build_rig() -> void:
	var background := ColorRect.new()
	background.position = Vector2.ZERO
	background.size = Vector2(960, 600)
	background.color = Color("161927")
	background.z_index = -100
	root.add_child(background)

	rig_root = Node2D.new()
	rig_root.position = Vector2(300, 250)
	rig_root.scale = Vector2(6, 6)
	root.add_child(rig_root)

	skeleton = Skeleton2D.new()
	skeleton.name = "MilestoneSkeleton"
	rig_root.add_child(skeleton)
	var root_bone := Bone2D.new()
	root_bone.name = "root"
	root_bone.position = Vector2.ZERO
	root_bone.scale = Vector2.ONE
	root_bone.length = 1.0
	skeleton.add_child(root_bone)

	core_sprite = Sprite2D.new()
	core_sprite.texture = load(CUTOUT_DIR + "core.png") as Texture2D
	core_sprite.position = Vector2(32, 32)
	core_sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	core_sprite.z_index = 10
	rig_root.add_child(core_sprite)

	for part_name in ["left_hand", "right_hand", "left_foot", "right_foot"]:
		var part_info: Dictionary = manifest["parts"][part_name]
		var bone := Bone2D.new()
		bone.name = part_name
		bone.scale = Vector2.ONE
		bone.length = 1.0
		bone.z_index = int(part_info["z_order"])
		root_bone.add_child(bone)
		var sprite := Sprite2D.new()
		sprite.texture = load(CUTOUT_DIR + part_name + ".png") as Texture2D
		sprite.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		var bbox: Array = part_info["source_bbox"]
		var source_center: Array = part_info["source_center"]
		# The bone is placed at the authored part center.  The crop texture is
		# centered on its crop bbox, so offset the sprite from bbox center back
		# to the authored anchor.  The previous sign was reversed and made the
		# offset rotate outward as the limb rotated.
		sprite.position = Vector2(
			float(source_center[0]) - (float(bbox[0]) + float(bbox[2])) / 2.0,
			float(source_center[1]) - (float(bbox[1]) + float(bbox[3])) / 2.0
		)
		bone.add_child(sprite)
		bones[part_name] = bone
		limb_sprites[part_name] = sprite


func _apply_pose(frame_index: int) -> void:
	var frame: Dictionary = workflow["frames"][frame_index]
	for part_name in bones.keys():
		var part: Dictionary = frame["parts"][part_name]
		var source_part: Dictionary = manifest["parts"][part_name]
		var bone: Bone2D = bones[part_name]
		bone.position = Vector2(float(part["x"]), float(part["y"]))
		bone.rotation = deg_to_rad(float(part["angle"]) - float(source_part["source_angle"]))


func _clear_output() -> void:
	var directory_path := ProjectSettings.globalize_path(OUTPUT_ROOT + workflow_name)
	DirAccess.make_dir_recursive_absolute(directory_path)
	var directory := DirAccess.open(directory_path)
	if directory == null:
		return
	for filename in directory.get_files():
		if filename.ends_with(".png"):
			directory.remove(filename)


func _capture_frame(frame_index: int) -> void:
	var image := root.get_viewport().get_texture().get_image()
	var output_path := ProjectSettings.globalize_path(
		"%s%s/frame_%04d.png" % [OUTPUT_ROOT, workflow_name, frame_index]
	)
	var result := image.save_png(output_path)
	if result != OK:
		_fail("could not save " + output_path)


func _fail(message: String) -> void:
	push_error("SKELETON_WORKFLOW_CAPTURE_FAIL: " + message)
	quit(1)
