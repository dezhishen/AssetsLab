extends SceneTree
const MODEL:=preload("res://scripts/back_skeleton_stage.gd")
const OUTPUT_PATH:="res://test_output/skeleton_pipeline/back_base.png"
func _init()->void: call_deferred("_run")
func _run()->void:
	var m:=MODEL.new(); root.add_child(m); await process_frame; await process_frame
	var errors:=m.validate_back_base()
	if not errors.is_empty(): push_error("BACK_SKELETON_STAGE_FAIL: "+"; ".join(errors)); quit(1); return
	var image:=root.get_texture().get_image(); var path:=ProjectSettings.globalize_path(OUTPUT_PATH); DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	if image==null or image.is_empty() or image.get_size()!=Vector2i(960,600) or image.save_png(path)!=OK: push_error("BACK_SKELETON_STAGE_FAIL: invalid capture"); quit(1); return
	print("BACK_SKELETON_STAGE_PASS symmetry=verified baseline=shared output=%s"%path); quit(0)
