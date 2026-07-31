extends SceneTree
const MODEL := preload("res://scripts/back_leg_cycle_stage.gd")
const OUTPUT_DIRECTORY := "res://test_output/skeleton_pipeline/back_legs"
func _init() -> void: call_deferred("_run")
func _run() -> void:
	var model := MODEL.new(); root.add_child(model); await process_frame
	var errors := model.validate()
	if not errors.is_empty(): push_error("BACK_LEG_FAIL: " + "; ".join(errors)); quit(1); return
	var directory_path := ProjectSettings.globalize_path(OUTPUT_DIRECTORY); DirAccess.make_dir_recursive_absolute(directory_path)
	for index in range(8):
		model.frame_index = index; await process_frame
		var image := root.get_texture().get_image()
		if image == null or image.is_empty() or image.save_png(directory_path.path_join("frame_%02d.png" % index)) != OK: push_error("BACK_LEG_FAIL: invalid frame %d" % index); quit(1); return
	print("BACK_LEG_CYCLE_PASS frames=8"); quit(0)
