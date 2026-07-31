extends SceneTree
const MODEL := preload("res://scripts/side_arm_swing_stage.gd")
const OUTPUT_DIRECTORY := "res://test_output/skeleton_pipeline/side_arm_swing"
func _init() -> void: call_deferred("_run")
func _run() -> void:
	var model := MODEL.new(); root.add_child(model); await process_frame
	var errors := model.validate_side_arm_swing()
	if not errors.is_empty(): push_error("SIDE_ARM_SWING_STAGE_FAIL: " + "; ".join(errors)); quit(1); return
	var directory_path := ProjectSettings.globalize_path(OUTPUT_DIRECTORY); DirAccess.make_dir_recursive_absolute(directory_path); var directory := DirAccess.open(directory_path)
	for file_name in directory.get_files():
		if file_name.begins_with("frame_") and file_name.ends_with(".png"): directory.remove(file_name)
	for index in range(8):
		model.frame_index=index; await process_frame; var image:=root.get_texture().get_image()
		if image==null or image.is_empty() or image.get_size()!=Vector2i(960,600) or image.save_png(directory_path.path_join("frame_%02d.png"%index))!=OK: push_error("SIDE_ARM_SWING_STAGE_FAIL: invalid frame %d"%index); quit(1); return
	print("SIDE_ARM_SWING_STAGE_PASS frames=8 lower_body=side_pelvis_unchanged arms=counterphase output=%s"%directory_path); quit(0)
