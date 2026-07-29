extends CharacterBody2D

signal bomb_requested

@export var move_speed: float = 180.0
@export var walk_fps: float = 10.0

var spawn_position := Vector2.ZERO
var direction_row := 0
var walk_phase := 0.0
var space_was_down := false
var variant := "male"
var body_frame_textures: Array[Texture2D] = []
var head_frame_textures: Array[Texture2D] = []

@onready var body_sprite: Sprite2D = $BodySprite
@onready var head_sprite: Sprite2D = $HeadSprite


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
	body_frame_textures.clear()
	head_frame_textures.clear()
	for row in range(4):
		for column in range(8):
			var body_path := "res://assets/characters/chibi/body_frames/walk_row%d_frame%d.png" % [row, column]
			var head_path := "res://assets/characters/chibi/head_%s_frames/walk_row%d_frame%d.png" % [variant, row, column]
			var body_texture := load(body_path) as Texture2D
			var head_texture := load(head_path) as Texture2D
			if body_texture == null:
				push_error("Missing character body frame: " + body_path)
			else:
				body_frame_textures.append(body_texture)
			if head_texture == null:
				push_error("Missing character head frame: " + head_path)
			else:
				head_frame_textures.append(head_texture)


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
		# The generated side-view rows face right on row 1 and left on row 3.
		direction_row = 1 if input_vector.x > 0.0 else 3
	else:
		direction_row = 0 if input_vector.y > 0.0 else 2


func _update_walk_frame(delta: float, is_moving: bool) -> void:
	if is_moving:
		walk_phase = fmod(walk_phase + delta * walk_fps, 8.0)
	else:
		walk_phase = 0.0
	_apply_frame(int(walk_phase))


func _apply_frame(frame: int) -> void:
	if body_frame_textures.is_empty() or head_frame_textures.is_empty():
		return
	var index := direction_row * 8 + posmod(frame, 8)
	body_sprite.texture = body_frame_textures[index]
	head_sprite.texture = head_frame_textures[index]


func _update_bomb_input() -> void:
	var space_is_down := Input.is_key_pressed(KEY_SPACE)
	if space_is_down and not space_was_down:
		bomb_requested.emit()
	space_was_down = space_is_down


func reset_to_spawn() -> void:
	global_position = spawn_position
	velocity = Vector2.ZERO
