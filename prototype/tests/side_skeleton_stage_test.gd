extends SceneTree

const MODEL := preload("res://scripts/side_skeleton_stage.gd")
const OUTPUT_PATH := "res://test_output/skeleton_pipeline/side_base.png"


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var model := MODEL.new()
	root.add_child(model)
	await process_frame
	await process_frame
	var errors := model.validate_side_base()
	if not errors.is_empty():
		_fail("; ".join(errors))
		return
	var image := root.get_texture().get_image()
	if image == null or image.is_empty() or image.get_size() != Vector2i(960, 600):
		_fail("invalid viewport image")
		return
	var output_path := ProjectSettings.globalize_path(OUTPUT_PATH)
	DirAccess.make_dir_recursive_absolute(output_path.get_base_dir())
	if image.save_png(output_path) != OK:
		_fail("could not save the side base capture")
		return
	print("SIDE_SKELETON_STAGE_PASS facing=right baseline=shared output=%s" % output_path)
	quit(0)


func _fail(message: String) -> void:
	push_error("SIDE_SKELETON_STAGE_FAIL: " + message)
	quit(1)
