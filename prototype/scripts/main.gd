extends Node2D

const ARENA_SIZE := Vector2(960.0, 600.0)
const WALL_RECTS := [
	Rect2(0.0, 0.0, 960.0, 24.0),
	Rect2(0.0, 576.0, 960.0, 24.0),
	Rect2(0.0, 0.0, 24.0, 600.0),
	Rect2(936.0, 0.0, 24.0, 600.0),
	Rect2(250.0, 160.0, 160.0, 24.0),
	Rect2(550.0, 160.0, 160.0, 24.0),
	Rect2(250.0, 416.0, 160.0, 24.0),
	Rect2(550.0, 416.0, 160.0, 24.0),
	Rect2(468.0, 250.0, 24.0, 100.0),
]

var player: CharacterBody2D
var bomb_scene := preload("res://scripts/bomb.gd")
var has_bomb := false


func _ready() -> void:
	player = $Player
	player.bomb_requested.connect(_on_player_bomb_requested)
	for wall_rect in WALL_RECTS:
		_add_wall(wall_rect)
	queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, ARENA_SIZE), Color("151a2c"))
	for x in range(24, 960, 64):
		draw_line(Vector2(x, 24), Vector2(x, 576), Color("202741"), 1.0)
	for y in range(24, 600, 64):
		draw_line(Vector2(24, y), Vector2(936, y), Color("202741"), 1.0)
	for wall_rect in WALL_RECTS:
		draw_rect(wall_rect, Color("3a4262"))
		draw_rect(wall_rect.grow(-3.0), Color("272e4b"))


func _add_wall(wall_rect: Rect2) -> void:
	var wall := StaticBody2D.new()
	wall.name = "Wall_%s_%s" % [int(wall_rect.position.x), int(wall_rect.position.y)]
	wall.position = wall_rect.position + wall_rect.size * 0.5
	var collision := CollisionShape2D.new()
	var shape := RectangleShape2D.new()
	shape.size = wall_rect.size
	collision.shape = shape
	wall.add_child(collision)
	add_child(wall)


func _on_player_bomb_requested() -> void:
	if has_bomb:
		return
	has_bomb = true
	var bomb := bomb_scene.new()
	bomb.global_position = player.global_position
	bomb.exploded.connect(_on_bomb_exploded)
	add_child(bomb)


func _on_bomb_exploded(world_position: Vector2) -> void:
	has_bomb = false
	if player.global_position.distance_to(world_position) < 82.0:
		player.reset_to_spawn()
