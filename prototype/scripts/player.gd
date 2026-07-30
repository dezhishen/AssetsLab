extends CharacterBody2D

signal bomb_requested

@export var move_speed: float = 180.0
@export var walk_fps: float = 8.0

var spawn_position := Vector2.ZERO
var direction_row := 0
var walk_phase := 0.0
var space_was_down := false
var variant := "male"
var asset_root := "chibi"
var appearance_seed: int = 20260730
var appearance_variant: int = 0
var torso_frame_textures: Array[Texture2D] = []
var arms_frame_textures: Array[Texture2D] = []
var lower_body_frame_textures: Array[Texture2D] = []
var feet_frame_textures: Array[Texture2D] = []
var head_frame_textures: Array[Texture2D] = []
var ear_frame_textures: Array[Texture2D] = []
var face_frame_textures: Array[Texture2D] = []

@onready var torso_sprite: Sprite2D = $BodySprite
@onready var arms_sprite: Sprite2D = $ArmsSprite
@onready var lower_body_sprite: Sprite2D = $LowerBodySprite
@onready var feet_sprite: Sprite2D = $FeetSprite
@onready var ear_sprite: Sprite2D = $EarSprite
@onready var head_sprite: Sprite2D = $HeadSprite
@onready var face_sprite: Sprite2D = $FaceSprite

func _ready() -> void:
	variant = "female" if "--female" in OS.get_cmdline_args() else "male"
	asset_root = "chibi_compact" if "--compact" in OS.get_cmdline_args() else "chibi"
	appearance_seed = _read_appearance_seed()
	appearance_variant = appearance_variant_for_seed(appearance_seed, variant == "female")
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
	torso_frame_textures.clear()
	arms_frame_textures.clear()
	lower_body_frame_textures.clear()
	feet_frame_textures.clear()
	head_frame_textures.clear()
	ear_frame_textures.clear()
	face_frame_textures.clear()
	for row in range(4):
		for column in range(8):
			var base_path := "res://assets/characters/%s/" % asset_root
			var torso_path := base_path + "torso_frames/walk_row%d_frame%d.png" % [row, column]
			var arms_path := base_path + "arms_frames/walk_row%d_frame%d.png" % [row, column]
			var lower_body_path := base_path + "lower_body_frames/walk_row%d_frame%d.png" % [row, column]
			var feet_path := base_path + "feet_frames/walk_row%d_frame%d.png" % [row, column]
			var head_path := base_path + "head_%s_frames/walk_row%d_frame%d.png" % [variant, row, column]
			var ear_path := "res://assets/characters/faces/ear_%02d/frames/walk_row%d_frame%d.png" % [appearance_variant, row, column]
			var face_path := "res://assets/characters/faces/face_%02d/frames/walk_row%d_frame%d.png" % [appearance_variant, row, column]
			var torso_texture := load(torso_path) as Texture2D
			var arms_texture := load(arms_path) as Texture2D
			var lower_body_texture := load(lower_body_path) as Texture2D
			var feet_texture := load(feet_path) as Texture2D
			var head_texture := load(head_path) as Texture2D
			var ear_texture := load(ear_path) as Texture2D
			var face_texture := load(face_path) as Texture2D
			if torso_texture == null:
				push_error("Missing character torso frame: " + torso_path)
			else:
				torso_frame_textures.append(torso_texture)
			if arms_texture == null:
				push_error("Missing character arms frame: " + arms_path)
			else:
				arms_frame_textures.append(arms_texture)
			if lower_body_texture == null:
				push_error("Missing character lower body frame: " + lower_body_path)
			else:
				lower_body_frame_textures.append(lower_body_texture)
			if feet_texture == null:
				push_error("Missing character feet frame: " + feet_path)
			else:
				feet_frame_textures.append(feet_texture)
			if head_texture == null:
				push_error("Missing character head frame: " + head_path)
			else:
				head_frame_textures.append(head_texture)
			if ear_texture == null:
				push_error("Missing character ear frame: " + ear_path)
			else:
				ear_frame_textures.append(ear_texture)
			if face_texture == null:
				push_error("Missing character face frame: " + face_path)
			else:
				face_frame_textures.append(face_texture)


func _read_appearance_seed() -> int:
	for argument in OS.get_cmdline_args():
		if argument.begins_with("--appearance-seed="):
			return argument.trim_prefix("--appearance-seed=").to_int()
	return appearance_seed


func appearance_variant_for_seed(seed: int, female_presenting: bool = false) -> int:
	var state: int = posmod(seed * 1103515245 + 12345, 2147483647)
	var candidates: Array[int] = [0, 1, 2, 3, 4, 5, 6, 7]
	if not female_presenting:
		# Blush variants are reserved for the female-presenting base in this
		# experiment so the two bases remain visually distinguishable without
		# introducing gendered body geometry.
		candidates = [0, 2, 4, 6]
	return candidates[state % candidates.size()]


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
	_apply_frame(int(walk_phase))


func _apply_frame(frame: int) -> void:
	if torso_frame_textures.is_empty() or arms_frame_textures.is_empty() or lower_body_frame_textures.is_empty() or feet_frame_textures.is_empty() or head_frame_textures.is_empty() or ear_frame_textures.is_empty() or face_frame_textures.is_empty():
		return
	var index := direction_row * 8 + posmod(frame, 8)
	torso_sprite.texture = torso_frame_textures[index]
	arms_sprite.texture = arms_frame_textures[index]
	lower_body_sprite.texture = lower_body_frame_textures[index]
	feet_sprite.texture = feet_frame_textures[index]
	ear_sprite.texture = ear_frame_textures[index]
	head_sprite.texture = head_frame_textures[index]
	face_sprite.texture = face_frame_textures[index]
	# Keep the head on the shared registration point until the source poses
	# themselves have been validated. This prevents a runtime transform from
	# disguising a source-frame alignment error as motion.
	head_sprite.position = Vector2(0, -26)
	ear_sprite.position = Vector2(0, -26)
	face_sprite.position = Vector2(0, -26)


func _update_bomb_input() -> void:
	var space_is_down := Input.is_key_pressed(KEY_SPACE)
	if space_is_down and not space_was_down:
		bomb_requested.emit()
	space_was_down = space_is_down


func reset_to_spawn() -> void:
	global_position = spawn_position
	velocity = Vector2.ZERO
