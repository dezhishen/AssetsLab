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
var base_features := false
var rebuild_head := false
var rebuild_body := false
var rgs_body_right := false
var bombo_body_right := false
var rgs_walk_reference := false
var milestone_body_right := false
var latest_generated_body := false
var vertical_body_candidate := false
var skin_mode := false
var skin_view := "front"
var skin_pack := ""
var skin_frames: Array[Texture2D] = []
var skin_sprite: Sprite2D
var artifacts_dir := ""
var layer_y := -26.0
var appearance_seed: int = 20260730
var appearance_variant: int = 0
var body_anchor_offsets: Dictionary = {}
var torso_frame_textures: Array[Texture2D] = []
var arms_frame_textures: Array[Texture2D] = []
var lower_body_frame_textures: Array[Texture2D] = []
var feet_frame_textures: Array[Texture2D] = []
var head_frame_textures: Array[Texture2D] = []
var ear_frame_textures: Array[Texture2D] = []
var face_frame_textures: Array[Texture2D] = []
var rgs_walk_reference_frame_textures: Array[Texture2D] = []
var milestone_body_frame_textures: Array[Texture2D] = []
var latest_generated_body_frame_textures: Array[Texture2D] = []
var vertical_front_frame_textures: Array[Texture2D] = []
var vertical_back_frame_textures: Array[Texture2D] = []

@onready var torso_sprite: Sprite2D = $BodySprite
@onready var arms_sprite: Sprite2D = $ArmsSprite
@onready var lower_body_sprite: Sprite2D = $LowerBodySprite
@onready var feet_sprite: Sprite2D = $FeetSprite
@onready var ear_sprite: Sprite2D = $EarSprite
@onready var head_sprite: Sprite2D = $HeadSprite
@onready var face_sprite: Sprite2D = $FaceSprite
@onready var rgs_walk_reference_sprite: Sprite2D = $RgsWalkReferenceSprite

func _ready() -> void:
	var user_args := OS.get_cmdline_user_args()
	variant = "female" if "--female" in user_args else "male"
	asset_root = "chibi_compact" if "--compact" in user_args else "chibi"
	base_features = "--base-features" in user_args
	rebuild_head = "--rebuild-head" in user_args
	rebuild_body = "--rebuild-body" in user_args
	rgs_body_right = "--rgs-body-right" in user_args
	bombo_body_right = "--bombo-body-right" in user_args
	rgs_walk_reference = "--rgs-walk-reference" in user_args
	milestone_body_right = "--milestone-body-right" in user_args
	latest_generated_body = "--latest-generated-body" in user_args
	vertical_body_candidate = "--vertical-body-candidate" in user_args
	skin_mode = "--skin-mode" in user_args
	for argument in user_args:
		if argument.begins_with("--skin-view="):
			skin_view = argument.trim_prefix("--skin-view=")
		if argument.begins_with("--skin-pack="):
			skin_pack = argument.trim_prefix("--skin-pack=")
	# --artifacts 支持两种写法：`--artifacts=dist/x` 或 `--artifacts dist/x`（空格）。
	# 之前只认等号，build_demo.sh 用空格传参会被静默忽略，回退到内置素材。
	var i := 0
	while i < user_args.size():
		var argument: String = user_args[i]
		var value: String = ""
		if argument.begins_with("--artifacts="):
			value = argument.trim_prefix("--artifacts=")
		elif argument == "--artifacts" and i + 1 < user_args.size():
			value = user_args[i + 1]
			i += 1
		if not value.is_empty():
			artifacts_dir = value
			# Image.load_from_file needs an OS path; resolve relative values
			# against the launch directory (repository root) so dist/ works
			# regardless of --path.
			if not artifacts_dir.is_absolute_path():
				var project_root := ProjectSettings.globalize_path("res://")
				var repo_root := project_root.trim_suffix("/").get_base_dir()
				artifacts_dir = repo_root.path_join(artifacts_dir)
		i += 1
	appearance_seed = _read_appearance_seed()
	appearance_variant = appearance_variant_for_seed(appearance_seed, variant == "female")
	_load_frame_textures()
	_load_rgs_walk_reference_frames()
	_load_milestone_body_frames()
	_load_latest_generated_body_frames()
	_load_vertical_body_candidate_frames()
	_load_body_anchor_offsets()
	if skin_mode:
		_load_skin_preview_frames()
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


func _load_artifacts_frames() -> void:
	# Load a dist/<workflow_id>/ artifact package directly from absolute paths
	# (no Godot import step required). Layer names match the export layout.
	torso_frame_textures.clear()
	arms_frame_textures.clear()
	lower_body_frame_textures.clear()
	feet_frame_textures.clear()
	head_frame_textures.clear()
	ear_frame_textures.clear()
	face_frame_textures.clear()
	var layers := {
		"feet": feet_frame_textures,
		"lower_body": lower_body_frame_textures,
		"arms": arms_frame_textures,
		"torso": torso_frame_textures,
		"head_base": head_frame_textures,
		"ear": ear_frame_textures,
		"face": face_frame_textures,
	}
	var manifest_path := artifacts_dir.path_join("runtime_manifest.json")
	if FileAccess.file_exists(manifest_path):
		var payload = JSON.parse_string(FileAccess.get_file_as_string(manifest_path))
		if payload is Dictionary:
			body_anchor_offsets = payload.get("head_anchor_offsets", {})
			var params = payload.get("runtime_params", {})
			if params is Dictionary:
				if params.get("move_speed") is float:
					move_speed = params["move_speed"]
				if params.get("walk_fps") is float:
					walk_fps = params["walk_fps"]
				if params.get("layer_y") is float:
					layer_y = params["layer_y"]
	for layer in layers:
		for row in range(4):
			for frame in range(8):
				var path := artifacts_dir.path_join("atlas/%s/walk_row%d_frame%d.png" % [layer, row, frame])
				var image := Image.load_from_file(path)
				if image == null:
					push_error("Missing artifact frame: " + path)
				else:
					layers[layer].append(ImageTexture.create_from_image(image))
	# 确认制品加载（每层 4x8=32 帧）
	var loaded := 0
	for layer in layers:
		loaded += layers[layer].size()
	print("ARTIFACTS_LOADED dir=", artifacts_dir, " layers=", layers.size(), " frames=", loaded)
	rebuild_head = true


func _load_frame_textures() -> void:
	if not artifacts_dir.is_empty():
		_load_artifacts_frames()
		return
	torso_frame_textures.clear()
	arms_frame_textures.clear()
	lower_body_frame_textures.clear()
	feet_frame_textures.clear()
	head_frame_textures.clear()
	ear_frame_textures.clear()
	face_frame_textures.clear()
	for row in range(4):
		for column in range(8):
			var direction_names: Array[String] = ["front", "right", "back", "left"]
			var direction_name: String = direction_names[row]
			var body_root := asset_root
			var body_base_path := "res://assets/characters/%s/" % body_root
			var head_base_path := "res://assets/characters/%s/" % asset_root
			var torso_path: String
			var arms_path: String
			var lower_body_path: String
			var feet_path: String
			if rebuild_body:
				var rebuild_body_path := "res://assets/characters/rebuild_body_v2/"
				torso_path = rebuild_body_path + "torso/%s_frame%d.png" % [direction_name, column]
				arms_path = rebuild_body_path + "arms/%s_frame%d.png" % [direction_name, column]
				lower_body_path = rebuild_body_path + "lower_body/%s_frame%d.png" % [direction_name, column]
				feet_path = rebuild_body_path + "feet/%s_frame%d.png" % [direction_name, column]
				if rgs_body_right and row == 1:
					var rgs_body_path := "res://assets/characters/rebuild_body_v5_rgs/"
					torso_path = rgs_body_path + "torso/right_frame%d.png" % column
					arms_path = rgs_body_path + "arms/right_frame%d.png" % column
					lower_body_path = rgs_body_path + "lower_body/right_frame%d.png" % column
					feet_path = rgs_body_path + "feet/right_frame%d.png" % column
				if bombo_body_right and row == 1:
					var bombo_body_path := "res://assets/characters/rebuild_body_v6_bombo/"
					torso_path = bombo_body_path + "torso/right_frame%d.png" % column
					arms_path = bombo_body_path + "arms/right_frame%d.png" % column
					lower_body_path = bombo_body_path + "lower_body/right_frame%d.png" % column
					feet_path = bombo_body_path + "feet/right_frame%d.png" % column
			else:
				torso_path = body_base_path + "torso_frames/walk_row%d_frame%d.png" % [row, column]
				arms_path = body_base_path + "arms_frames/walk_row%d_frame%d.png" % [row, column]
				lower_body_path = body_base_path + "lower_body_frames/walk_row%d_frame%d.png" % [row, column]
				feet_path = body_base_path + "feet_frames/walk_row%d_frame%d.png" % [row, column]
			var head_path := head_base_path + "head_%s_frames/walk_row%d_frame%d.png" % [variant, row, column]
			var ear_path: String
			var face_path: String
			if rebuild_head:
				var rebuild_base := "res://assets/characters/rebuild_atlas_v1_runtime/male/"
				head_path = rebuild_base + "face_base_frames/walk_row%d_frame%d.png" % [row, column]
				ear_path = rebuild_base + "ears_frames/walk_row%d_frame%d.png" % [row, column]
				face_path = rebuild_base + "face_frames/walk_row%d_frame%d.png" % [row, column]
			elif base_features:
				var feature_base := "res://assets/characters/base_features_v1/%s/" % variant
				ear_path = feature_base + "ear_frames/walk_row%d_frame%d.png" % [row, column]
				face_path = feature_base + "face_frames/walk_row%d_frame%d.png" % [row, column]
			else:
				ear_path = "res://assets/characters/faces/ear_%02d/frames/walk_row%d_frame%d.png" % [appearance_variant, row, column]
				face_path = "res://assets/characters/faces/face_%02d/frames/walk_row%d_frame%d.png" % [appearance_variant, row, column]
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
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--appearance-seed="):
			return argument.trim_prefix("--appearance-seed=").to_int()
	return appearance_seed


func _load_body_anchor_offsets() -> void:
	if not artifacts_dir.is_empty():
		# 制品模式：head 层帧已在 cell 内与 body 对齐（烘焙时统一 bbox 变换），
		# 偏移应为 0——制品 manifest 的 head_anchor_offsets 已由 _load_artifacts_frames
		# 读入 body_anchor_offsets。内置素材的校准偏移只适用于内置素材，强行套用
		# 会让脑袋相对身体偏移（歪）。
		return
	body_anchor_offsets.clear()
	if not rebuild_head:
		return
	var file := FileAccess.open("res://assets/characters/rebuild_atlas_v1_runtime/male/runtime_manifest.json", FileAccess.READ)
	if file == null:
		return
	var payload = JSON.parse_string(file.get_as_text())
	if not payload is Dictionary:
		return
	var offsets = payload.get("body_anchor_offsets", {})
	if offsets is Dictionary:
		body_anchor_offsets = offsets


func _load_rgs_walk_reference_frames() -> void:
	rgs_walk_reference_frame_textures.clear()
	if not rgs_walk_reference:
		return
	for frame in range(8):
		var path := "res://assets/characters/open_source/rgs_walk_reference/rgs_right_frame%d.png" % frame
		var texture := load(path) as Texture2D
		if texture == null:
			push_error("Missing RGS walk reference frame: " + path)
		else:
			rgs_walk_reference_frame_textures.append(texture)


func _load_milestone_body_frames() -> void:
	milestone_body_frame_textures.clear()
	if not milestone_body_right:
		return
	for frame in range(8):
		var path := "res://assets/characters/generated/body_outline_split_v2_manual_from_project/frame%d.png" % frame
		var texture := load(path) as Texture2D
		if texture == null:
			push_error("Missing milestone body frame: " + path)
		else:
			milestone_body_frame_textures.append(texture)


func _load_latest_generated_body_frames() -> void:
	latest_generated_body_frame_textures.clear()
	if not latest_generated_body:
		return
	var root := "res://assets/characters/generated/female_adventurer_reference_mannequin_v1_adapted/body_frames/"
	for row in range(4):
		for frame in range(8):
			var path := root + "walk_row%d_frame%d.png" % [row, frame]
			var texture := load(path) as Texture2D
			if texture == null:
				push_error("Missing latest generated body frame: " + path)
			else:
				latest_generated_body_frame_textures.append(texture)


func _load_vertical_body_candidate_frames() -> void:
	vertical_front_frame_textures.clear()
	vertical_back_frame_textures.clear()
	if not vertical_body_candidate:
		return
	for frame in range(8):
		var front_path := "res://assets/characters/generated/body_vertical_update_v1/runtime/front_frames/frame%d.png" % frame
		var back_path := "res://assets/characters/generated/body_vertical_update_v1/runtime/back_frames/frame%d.png" % frame
		var front_texture := load(front_path) as Texture2D
		var back_texture := load(back_path) as Texture2D
		if front_texture == null:
			push_error("Missing vertical front body frame: " + front_path)
		else:
			vertical_front_frame_textures.append(front_texture)
		if back_texture == null:
			push_error("Missing vertical back body frame: " + back_path)
		else:
			vertical_back_frame_textures.append(back_texture)


func _load_skin_preview_frames() -> void:
	# 蒙皮预览：优先加载独立皮肤包 skins/<id>/preview/<skin>_<motion>_<view>/frameN.png
	# （skin.py render 输出到皮肤包 preview/）；否则回退 dist/<id>/skins/。
	# 用 --skin-view 指定 front/side/back（默认 front）。
	skin_frames.clear()
	var skins_root := ""
	if not skin_pack.is_empty():
		var project_root := ProjectSettings.globalize_path("res://")
		var repo_root := project_root.trim_suffix("/").get_base_dir()
		skins_root = repo_root.path_join("skins").path_join(skin_pack).path_join("preview")
	elif not artifacts_dir.is_empty():
		skins_root = artifacts_dir.path_join("skins")
	else:
		return
	var dir := DirAccess.open(skins_root)
	if dir == null:
		push_warning("Skin preview: no directory " + skins_root)
		return
	var seq_name := ""
	dir.list_dir_begin()
	while true:
		var name := dir.get_next()
		if name == "":
			break
		# 序列目录名含视图（front/side/back），如 mannequin_walk_front
		if dir.current_is_dir() and name.contains(skin_view):
			seq_name = name
	dir.list_dir_end()
	if seq_name.is_empty():
		push_warning("Skin preview: no sequence for view '" + skin_view + "' under " + skins_root)
		return
	var seq_path := skins_root.path_join(seq_name)
	var frame_dir := DirAccess.open(seq_path)
	if frame_dir == null:
		return
	var frame_paths: Array[String] = []
	frame_dir.list_dir_begin()
	while true:
		var file := frame_dir.get_next()
		if file == "":
			break
		if file.begins_with("frame") and file.ends_with(".png"):
			frame_paths.append(seq_path.path_join(file))
	frame_dir.list_dir_end()
	frame_paths.sort()
	for path in frame_paths:
		var image := Image.load_from_file(path)
		if image != null:
			skin_frames.append(ImageTexture.create_from_image(image))
	if skin_frames.is_empty():
		return
	skin_sprite = Sprite2D.new()
	skin_sprite.name = "SkinPreview"
	skin_sprite.z_index = 60
	add_child(skin_sprite)
	print("SKIN_PREVIEW_FRAMES=%d seq=%s" % [skin_frames.size(), seq_path])


func _current_body_anchor_offset() -> Vector2:
	if not rebuild_head:
		return Vector2.ZERO
	var names := ["front", "right", "back", "left"]
	var value = body_anchor_offsets.get(names[direction_row], [0, 0])
	if value is Array and value.size() >= 2:
		return Vector2(float(value[0]), float(value[1]))
	return Vector2.ZERO


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
	if skin_mode and not skin_frames.is_empty() and skin_sprite != null:
		for sprite in [torso_sprite, arms_sprite, lower_body_sprite, feet_sprite, ear_sprite, head_sprite, face_sprite, rgs_walk_reference_sprite]:
			sprite.visible = false
		skin_sprite.visible = true
		skin_sprite.texture = skin_frames[posmod(frame, skin_frames.size())]
		return
	if torso_frame_textures.is_empty() or arms_frame_textures.is_empty() or lower_body_frame_textures.is_empty() or feet_frame_textures.is_empty() or head_frame_textures.is_empty() or ear_frame_textures.is_empty() or face_frame_textures.is_empty():
		return
	var use_rgs_reference := rgs_walk_reference and direction_row == 1 and rgs_walk_reference_frame_textures.size() == 8
	rgs_walk_reference_sprite.visible = use_rgs_reference
	if use_rgs_reference:
		rgs_walk_reference_sprite.texture = rgs_walk_reference_frame_textures[posmod(frame, 8)]
		for sprite in [torso_sprite, arms_sprite, lower_body_sprite, feet_sprite, ear_sprite, head_sprite, face_sprite]:
			sprite.visible = false
		return
	var index := direction_row * 8 + posmod(frame, 8)
	var use_milestone_body := milestone_body_right and direction_row == 1 and milestone_body_frame_textures.size() == 8
	if use_milestone_body:
		torso_sprite.visible = true
		torso_sprite.texture = milestone_body_frame_textures[posmod(frame, 8)]
		for sprite in [arms_sprite, lower_body_sprite, feet_sprite, ear_sprite, head_sprite, face_sprite]:
			sprite.visible = false
		return
	var use_latest_generated_body := latest_generated_body and latest_generated_body_frame_textures.size() == 32
	var use_vertical_body_candidate := vertical_body_candidate and vertical_front_frame_textures.size() == 8 and vertical_back_frame_textures.size() == 8 and (direction_row == 0 or direction_row == 2)
	if use_vertical_body_candidate:
		torso_sprite.visible = true
		torso_sprite.texture = vertical_front_frame_textures[posmod(frame, 8)] if direction_row == 0 else vertical_back_frame_textures[posmod(frame, 8)]
		for sprite in [arms_sprite, lower_body_sprite, feet_sprite]:
			sprite.visible = false
		ear_sprite.visible = true
		head_sprite.visible = true
		face_sprite.visible = true
		ear_sprite.texture = ear_frame_textures[index]
		head_sprite.texture = head_frame_textures[index]
		face_sprite.texture = face_frame_textures[index]
		# The vertical candidate was normalized around the 64x64 center. The
		# adapter calibration offsets belong to the older body source and would
		# shift the head several pixels to the right on front/back views.
		var vertical_registered_position := Vector2(0.0, layer_y)
		head_sprite.position = vertical_registered_position
		ear_sprite.position = vertical_registered_position
		face_sprite.position = vertical_registered_position
		return
	if use_latest_generated_body:
		torso_sprite.visible = true
		torso_sprite.texture = latest_generated_body_frame_textures[index]
		for sprite in [arms_sprite, lower_body_sprite, feet_sprite]:
			sprite.visible = false
		ear_sprite.visible = true
		head_sprite.visible = true
		face_sprite.visible = true
		ear_sprite.texture = ear_frame_textures[index]
		head_sprite.texture = head_frame_textures[index]
		face_sprite.texture = face_frame_textures[index]
		var latest_body_offset := _current_body_anchor_offset()
		var latest_registered_position := Vector2(latest_body_offset.x, layer_y + latest_body_offset.y)
		head_sprite.position = latest_registered_position
		ear_sprite.position = latest_registered_position
		face_sprite.position = latest_registered_position
		return
	for sprite in [torso_sprite, arms_sprite, lower_body_sprite, feet_sprite, ear_sprite, head_sprite, face_sprite]:
		sprite.visible = true
	torso_sprite.texture = torso_frame_textures[index]
	arms_sprite.texture = arms_frame_textures[index]
	lower_body_sprite.texture = lower_body_frame_textures[index]
	feet_sprite.texture = feet_frame_textures[index]
	ear_sprite.texture = ear_frame_textures[index]
	head_sprite.texture = head_frame_textures[index]
	face_sprite.texture = face_frame_textures[index]
	# The body anchor page stores one shared offset per direction. All head
	# sublayers move together so calibration cannot separate ears from the face.
	var body_offset := _current_body_anchor_offset()
	var registered_position := Vector2(body_offset.x, layer_y + body_offset.y)
	head_sprite.position = registered_position
	ear_sprite.position = registered_position
	face_sprite.position = registered_position


func _update_bomb_input() -> void:
	var space_is_down := Input.is_key_pressed(KEY_SPACE)
	if space_is_down and not space_was_down:
		bomb_requested.emit()
	space_was_down = space_is_down


func reset_to_spawn() -> void:
	global_position = spawn_position
	velocity = Vector2.ZERO
