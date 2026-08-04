extends SceneTree


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var packed_scene := load("res://main.tscn") as PackedScene
	if packed_scene == null:
		_fail("main.tscn could not be loaded")
		return

	var instance := packed_scene.instantiate()
	root.add_child(instance)
	await process_frame

	var player := instance.get_node_or_null("Player") as CharacterBody2D
	var body_sprite := instance.get_node_or_null("Player/BodySprite") as Sprite2D
	var arms_sprite := instance.get_node_or_null("Player/ArmsSprite") as Sprite2D
	var lower_body_sprite := instance.get_node_or_null("Player/LowerBodySprite") as Sprite2D
	var feet_sprite := instance.get_node_or_null("Player/FeetSprite") as Sprite2D
	var ear_sprite := instance.get_node_or_null("Player/EarSprite") as Sprite2D
	var head_sprite := instance.get_node_or_null("Player/HeadSprite") as Sprite2D
	var face_sprite := instance.get_node_or_null("Player/FaceSprite") as Sprite2D
	var rgs_walk_reference_sprite := instance.get_node_or_null("Player/RgsWalkReferenceSprite") as Sprite2D
	if player == null or body_sprite == null or arms_sprite == null or lower_body_sprite == null or feet_sprite == null or ear_sprite == null or head_sprite == null or face_sprite == null or rgs_walk_reference_sprite == null:
		_fail("player scene nodes are missing")
		return
	if body_sprite.texture == null or arms_sprite.texture == null or lower_body_sprite.texture == null or feet_sprite.texture == null or ear_sprite.texture == null or head_sprite.texture == null or face_sprite.texture == null:
		_fail("layer frame textures are not loaded")
		return
	if player.torso_frame_textures.size() != 32 or player.arms_frame_textures.size() != 32 or player.lower_body_frame_textures.size() != 32 or player.feet_frame_textures.size() != 32 or player.head_frame_textures.size() != 32 or player.ear_frame_textures.size() != 32 or player.face_frame_textures.size() != 32:
		_fail("all body and appearance frame sets are not loaded as 32 separate frames")
		return
	var user_args := OS.get_cmdline_user_args()
	if "--rebuild-head" in user_args and not player.rebuild_head:
		_fail("rebuild head mode was not enabled")
		return
	if "--rebuild-body" in user_args and not player.rebuild_body:
		_fail("rebuild body mode was not enabled")
		return
	if "--rgs-body-right" in user_args:
		if not player.rgs_body_right:
			_fail("RGS body candidate mode was not enabled")
			return
		if player.torso_frame_textures.size() <= 8 or not player.torso_frame_textures[8].resource_path.contains("rebuild_body_v5_rgs"):
			_fail("RGS body candidate right-facing torso was not loaded")
			return
	if "--bombo-body-right" in user_args:
		if not player.bombo_body_right:
			_fail("Bombo body candidate mode was not enabled")
			return
		if player.torso_frame_textures.size() <= 8 or not player.torso_frame_textures[8].resource_path.contains("rebuild_body_v6_bombo"):
			_fail("Bombo body candidate right-facing torso was not loaded")
			return
	if "--milestone-body-right" in user_args:
		if not player.milestone_body_right or player.milestone_body_frame_textures.size() != 8:
			_fail("milestone body frames were not loaded")
			return
	if "--latest-generated-body" in user_args:
		if not player.latest_generated_body or player.latest_generated_body_frame_textures.size() != 32:
			_fail("latest generated body frames were not loaded")
			return
	if "--vertical-body-candidate" in user_args:
		if not player.vertical_body_candidate or player.vertical_front_frame_textures.size() != 8 or player.vertical_back_frame_textures.size() != 8:
			_fail("vertical body candidate frames were not loaded")
			return
	if "--rgs-walk-reference" in user_args:
		if not player.rgs_walk_reference or player.rgs_walk_reference_frame_textures.size() != 8:
			_fail("RGS walk reference frames were not loaded")
			return
	var appearance_a: int = player.appearance_variant_for_seed(123456)
	var appearance_b: int = player.appearance_variant_for_seed(123456)
	if appearance_a != appearance_b:
		_fail("same appearance seed produced different variants")
		return

	player._update_direction(Vector2.RIGHT)
	if player.direction_row != 1:
		_fail("right movement is mapped to the wrong side row")
		return
	player._apply_frame(0)
	if "--rgs-walk-reference" in user_args and not rgs_walk_reference_sprite.visible:
		_fail("RGS walk reference sprite was not activated")
		return
	player._update_direction(Vector2.LEFT)
	if player.direction_row != 3:
		_fail("left movement is mapped to the wrong side row")
		return
	player._update_direction(Vector2.UP)
	if player.direction_row != 2:
		_fail("up movement is mapped to the wrong back row")
		return

	player._update_direction(Vector2.DOWN)
	if "--vertical-body-candidate" in user_args:
		player._apply_frame(0)
		if not body_sprite.texture.resource_path.contains("body_vertical_update_v1/runtime/front_frames"):
			_fail("front vertical candidate was not selected")
			return
		player._update_direction(Vector2.UP)
		player._apply_frame(0)
		if not body_sprite.texture.resource_path.contains("body_vertical_update_v1/runtime/back_frames"):
			_fail("back vertical candidate was not selected")
			return
		player._update_direction(Vector2.DOWN)
	player._update_walk_frame(0.0, false)
	var first_frame := body_sprite.texture
	player._update_walk_frame(0.2, true)
	if body_sprite.texture == first_frame:
		_fail("walk frame did not advance while moving")
		return
	var phase_before_idle: float = player.walk_phase
	player._update_walk_frame(0.0, false)
	if player.walk_phase != phase_before_idle:
		_fail("walk phase reset when movement stopped")
		return
	# All visual layers share the scene's visual anchor (default -26px; the
	# artifact runtime_params can override it via player.layer_y). Rebuild
	# head mode adds its direction-specific calibration offset on top.
	var expected_head_position := Vector2(0.0, player.layer_y)
	if player.rebuild_head and not player.vertical_body_candidate:
		expected_head_position = player._current_body_anchor_offset()
		expected_head_position.y += player.layer_y
	if head_sprite.position != expected_head_position:
		_fail("head anchor drifted during frame application")
		return
	if ear_sprite.position != expected_head_position or face_sprite.position != expected_head_position:
		_fail("appearance layer anchor drifted during frame application")
		return

	var original_position := player.global_position
	player.velocity = Vector2(1.0, 0.0) * player.move_speed
	player.move_and_slide()
	if player.global_position.x <= original_position.x:
		_fail("player did not move in the smoke test")
		return

	print("SMOKE_TEST_PASS")
	quit(0)


func _fail(message: String) -> void:
	push_error("SMOKE_TEST_FAIL: " + message)
	quit(1)
