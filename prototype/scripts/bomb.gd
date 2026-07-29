extends Node2D

signal exploded(world_position: Vector2)

var fuse_seconds := 1.0
var blast_seconds := 0.28
var is_exploding := false


func _process(delta: float) -> void:
	if not is_exploding:
		fuse_seconds -= delta
		if fuse_seconds <= 0.0:
			is_exploding = true
			exploded.emit(global_position)
	else:
		blast_seconds -= delta
		if blast_seconds <= 0.0:
			queue_free()
	queue_redraw()


func _draw() -> void:
	if is_exploding:
		var blast_color := Color("f2c14e")
		draw_circle(Vector2.ZERO, 22.0, Color("f06b45"))
		draw_rect(Rect2(-54.0, -10.0, 108.0, 20.0), blast_color)
		draw_rect(Rect2(-10.0, -54.0, 20.0, 108.0), blast_color)
	else:
		var pulse := 1.0 + 0.08 * sin(fuse_seconds * 18.0)
		draw_circle(Vector2.ZERO, 12.0 * pulse, Color("25253d"))
		draw_circle(Vector2(-3.0, -4.0), 3.0, Color("f2c14e"))
		draw_line(Vector2(5.0, -10.0), Vector2(10.0, -18.0), Color("f06b45"), 3.0)
