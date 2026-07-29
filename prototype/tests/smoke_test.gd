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
	var leg_sprite := instance.get_node_or_null("Player/LegSprite") as Sprite2D
	var head_sprite := instance.get_node_or_null("Player/HeadSprite") as Sprite2D
	if player == null or body_sprite == null or leg_sprite == null or head_sprite == null:
		_fail("player scene nodes are missing")
		return
	if body_sprite.texture == null or leg_sprite.texture == null or head_sprite.texture == null:
		_fail("body/head frame textures are not loaded")
	if player.body_frame_textures.size() != 32 or player.leg_frame_textures.size() != 32 or player.head_frame_textures.size() != 32:
		_fail("body/leg/head frame sets are not loaded as 32 separate frames")
		return

	player._update_direction(Vector2.RIGHT)
	if player.direction_row != 1:
		_fail("right movement is mapped to the wrong side row")
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
	player._update_walk_frame(0.0, false)
	var first_frame := body_sprite.texture
	player._update_walk_frame(0.2, true)
	if body_sprite.texture == first_frame:
		_fail("walk frame did not advance while moving")
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
