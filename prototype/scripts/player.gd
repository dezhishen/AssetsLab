extends CharacterBody2D

signal bomb_requested

@export var move_speed: float = 180.0
@export var walk_fps: float = 8.0

var spawn_position := Vector2.ZERO
var direction_row := 0
var walk_phase := 0.0
var space_was_down := false
var variant := "male"
var frame_textures: Array[Texture2D] = []

@onready var body_sprite: Sprite2D = $BodySprite


func _ready() -> void:
	variant = "female" if "--female" in OS.get_cmdline_args() else "male"
	_load_frame_textures()
	spawn_position = global_position
	_apply_frame(0)


func _physics_process(delta: float) -> void:
	var input_vector := _read_keyboard_vector()
	velocity = input_vector * move_speed
	move_and_slide()
	global_position.x = clampf(global_position.x, 28.0, 932.0)
	global_position.y = clampf(global_position.y, 28.0, 572.0)

	_update_direction(input_vector)
	_update_walk_frame(delta, input_vector.length_squared() > 0.0)
	_update_bomb_input()


func _load_frame_textures() -> void:
	frame_textures.clear()
	for row in range(4):
		for column in range(4):
			var path := "res://assets/characters/%s/frames/walk_row%d_frame%d.png" % [variant, row, column]
			var texture := load(path) as Texture2D
			if texture == null:
				push_error("Missing character frame: " + path)
				continue
			frame_textures.append(texture)


func _read_keyboard_vector() -> Vector2:
	var horizontal := 0.0
	var vertical := 0.0
	if Input.is_key_pressed(KEY_A) or Input.is_key_pressed(KEY_LEFT):
		horizontal -= 1.0
	if Input.is_key_pressed(KEY_D) or Input.is_key_pressed(KEY_RIGHT):
		horizontal += 1.0
	if Input.is_key_pressed(KEY_W) or Input.is_key_pressed(KEY_UP):
		vertical -= 1.0
	if Input.is_key_pressed(KEY_S) or Input.is_key_pressed(KEY_DOWN):
		vertical += 1.0
	return Vector2(horizontal, vertical).normalized()


func _update_direction(input_vector: Vector2) -> void:
	if input_vector.length_squared() <= 0.0:
		return
	if absf(input_vector.x) > absf(input_vector.y):
		# The generated side-view rows face left on row 1 and right on row 3.
		direction_row = 3 if input_vector.x > 0.0 else 1
	else:
		direction_row = 0 if input_vector.y > 0.0 else 2


func _update_walk_frame(delta: float, is_moving: bool) -> void:
	if is_moving:
		walk_phase = fmod(walk_phase + delta * walk_fps, 4.0)
	else:
		walk_phase = 0.0
	_apply_frame(int(walk_phase))


func _apply_frame(frame: int) -> void:
	if frame_textures.is_empty():
		return
	var index := direction_row * 4 + posmod(frame, 4)
	body_sprite.texture = frame_textures[index]
	body_sprite.hframes = 1
	body_sprite.vframes = 1
	body_sprite.frame_coords = Vector2i.ZERO


func _update_bomb_input() -> void:
	var space_is_down := Input.is_key_pressed(KEY_SPACE)
	if space_is_down and not space_was_down:
		bomb_requested.emit()
	space_was_down = space_is_down


func reset_to_spawn() -> void:
	global_position = spawn_position
	velocity = Vector2.ZERO
