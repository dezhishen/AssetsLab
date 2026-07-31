extends SceneTree

const MODEL := preload("res://scripts/front_skeleton_stage.gd")
const OUTPUT_PATH := "res://test_output/skeleton_pipeline/front_base.png"


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var model := MODEL.new()
	root.add_child(model)
	await process_frame
	await process_frame

	var errors := model.validate_front_base()
	if not errors.is_empty():
		push_error("FRONT_SKELETON_STAGE_FAIL: " + "; ".join(errors))
		quit(1)
		return

	var absolute_path := ProjectSettings.globalize_path(OUTPUT_PATH)
	DirAccess.make_dir_recursive_absolute(absolute_path.get_base_dir())
	var image := root.get_texture().get_image()
	if image == null or image.is_empty():
		push_error("FRONT_SKELETON_STAGE_FAIL: viewport image is empty")
		quit(1)
		return
	if image.get_size() != Vector2i(960, 600):
		push_error("FRONT_SKELETON_STAGE_FAIL: unexpected viewport size %s" % image.get_size())
		quit(1)
		return
	if image.save_png(absolute_path) != OK:
		push_error("FRONT_SKELETON_STAGE_FAIL: could not save preview")
		quit(1)
		return
	print("FRONT_SKELETON_STAGE_PASS anchors=15 baseline=470 output=%s" % absolute_path)
	quit(0)
