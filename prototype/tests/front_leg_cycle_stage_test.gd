extends SceneTree

const MODEL := preload("res://scripts/front_leg_cycle_stage.gd")
const OUTPUT_DIRECTORY := "res://test_output/skeleton_pipeline/front_legs"


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var model := MODEL.new()
	root.add_child(model)
	await process_frame
	var errors := model.validate_leg_cycle()
	if not errors.is_empty():
		_fail("; ".join(errors))
		return

	var absolute_directory := ProjectSettings.globalize_path(OUTPUT_DIRECTORY)
	DirAccess.make_dir_recursive_absolute(absolute_directory)
	var directory := DirAccess.open(absolute_directory)
	if directory == null:
		_fail("could not open output directory")
		return
	for file_name in directory.get_files():
		if file_name.begins_with("frame_") and file_name.ends_with(".png"):
			directory.remove(file_name)

	for index in range(8):
		model.frame_index = index
		await process_frame
		var image := root.get_texture().get_image()
		if image == null or image.is_empty() or image.get_size() != Vector2i(960, 600):
			_fail("frame %d returned an invalid viewport image" % index)
			return
		var output_path := absolute_directory.path_join("frame_%02d.png" % index)
		if image.save_png(output_path) != OK:
			_fail("could not save frame %d" % index)
			return
	print("FRONT_LEG_CYCLE_STAGE_PASS frames=8 pelvis=static planted_foot=each_frame output=%s" % absolute_directory)
	quit(0)


func _fail(message: String) -> void:
	push_error("FRONT_LEG_CYCLE_STAGE_FAIL: " + message)
	quit(1)
