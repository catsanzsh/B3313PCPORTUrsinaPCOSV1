from ursina import (
    Ursina, Entity, camera, window, color, held_keys, mouse, time, clamp,
    Vec2, Vec3,
    Mesh, DirectionalLight, AmbientLight,
    destroy,
    Sky
)
from math import sin, cos, pi, radians, sqrt, atan2, degrees
from functools import lru_cache
import time as pytime

# --------- combine() compatibility fix ---------
def combine(entities, name=None):
    """Simplified combine function for compatibility"""
    if not entities:
        return None
    # Create a parent entity to hold all others
    parent = Entity(name=name or "combined")
    for e in entities:
        e.parent = parent
    return parent

# 🚀 Engine Bootstrap
app = Ursina(
    vsync=True,
    development_mode=False,
    size=(1280, 720),
    borderless=False,
    fullscreen=False
)

# Window configuration
window.title = "B3313 Engine - Comet Observatory (Stable)"
window.color = color.rgb(8, 10, 22)
window.fps_counter.enabled = True
window.entity_counter.enabled = True

# 🎨 Color Constants
class Colors:
    OBSERVATORY = color.rgba(210, 230, 255, 255)
    ENGINE = color.rgba(90, 90, 160, 240)
    GLASS = color.rgba(160, 220, 255, 120)
    STAR = color.yellow
    DOME_RED = color.rgb(200, 50, 50)
    DOME_GREEN = color.rgb(50, 150, 50)
    DOME_CYAN = color.rgb(50, 150, 200)
    METAL = color.rgb(100, 100, 100)
    ENERGY = color.rgb(100, 150, 255)

# 🌍 Physics Constants
class Physics:
    GRAVITY = 25
    PLANET_CENTER = Vec3(0, 0, 0)
    PLANET_RADIUS = 32
    PLAYER_HEIGHT = 2
    PLAYER_RADIUS = 0.5
    JUMP_HEIGHT = 5
    MOVE_SPEED = 7
    AIR_CONTROL = 0.8
    FRICTION = 0.9

class SphericalPlayer(Entity):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Movement properties
        self.speed = Physics.MOVE_SPEED
        self.jump_height = Physics.JUMP_HEIGHT
        self.height = Physics.PLAYER_HEIGHT
        self.velocity = Vec3(0, 0, 0)
        self.grounded = False
        self.start_pos = self.position.copy()
        self.collider = 'sphere'

        # Camera setup
        self.camera_pivot = Entity(parent=self, y=self.height/2)
        camera.parent = self.camera_pivot
        camera.position = Vec3(0, 0, 0)
        camera.rotation = Vec3(0, 0, 0)
        camera.fov = 90

        # Input setup
        mouse.locked = True
        self.mouse_sensitivity = Vec2(100, 100)

    @lru_cache(maxsize=128)
    def get_surface_normal(self, pos_tuple):
        """Cached surface normal calculation"""
        pos = Vec3(*pos_tuple)
        return (pos - Physics.PLANET_CENTER).normalized()

    def update(self):
        # Get surface normal (with caching)
        pos_tuple = (round(self.position.x, 2), round(self.position.y, 2), round(self.position.z, 2))
        surface_normal = self.get_surface_normal(pos_tuple)
        
        # Orient player to surface and handle mouse look
        self.look_at(self.position + surface_normal, Physics.PLANET_CENTER)
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity.x * time.dt

        # Mouse look (camera pitch)
        self.camera_pivot.rotation_x = clamp(
            self.camera_pivot.rotation_x - mouse.velocity[1] * self.mouse_sensitivity.y * time.dt,
            -90, 90
        )

        # Movement input
        move_input = Vec3(
            held_keys['d'] - held_keys['a'],
            0,
            held_keys['w'] - held_keys['s']
        ).normalized()

        move_direction = self.forward * move_input.z + self.right * move_input.x
        move_amount = move_direction * self.speed * (Physics.AIR_CONTROL if not self.grounded else 1.0)
        
        # Apply physics
        gravity_force = -surface_normal * Physics.GRAVITY
        self.velocity += gravity_force * time.dt

        # Apply movement
        self.position += (self.velocity + move_amount) * time.dt

        # Ground collision and correction
        distance_from_center = self.position.length()
        target_distance = Physics.PLANET_RADIUS + self.height / 2

        if distance_from_center <= target_distance:
            self.grounded = True
            self.position = self.position.normalized() * target_distance

            # Cancel radial velocity
            radial_velocity = self.velocity.dot(surface_normal)
            if radial_velocity < 0:
                self.velocity -= surface_normal * radial_velocity

            # Apply friction when not moving
            if move_input.length() == 0:
                self.velocity *= Physics.FRICTION
        else:
            self.grounded = False

    def jump(self):
        if self.grounded:
            self.velocity += self.up * self.jump_height
            self.grounded = False

    def reset_position(self):
        self.position = self.start_pos.copy()
        self.velocity = Vec3(0, 0, 0)
        self.rotation = Vec3(0, 0, 0)
        self.camera_pivot.rotation_x = 0
        print("Player reset to starting position")

class ObservatoryWorld:
    def __init__(self):
        self.entities = []
        self.animated_entities = []
        self.create_world()

    def create_world(self):
        # Skybox
        Sky(texture='sky_default', color=color.white * 0.8)

        # Main planetoid
        self.main_floor = Entity(
            model='sphere',
            scale=Physics.PLANET_RADIUS * 2,
            color=Colors.OBSERVATORY,
            collider='sphere'
        )
        self.entities.append(self.main_floor)

        # Create decorative elements
        self.create_decorative_cubes()
        self.create_domes()
        self.create_central_star()
        self.create_engine_room()

        # Lighting
        self.setup_lighting()

    def create_decorative_cubes(self):
        cubes = []
        for i in range(8):
            angle = i * (360 / 8)
            dir_vec = Vec3(cos(radians(angle)), 0, sin(radians(angle)))
            position = dir_vec * (Physics.PLANET_RADIUS - 0.2)

            cube = Entity(
                model='cube',
                color=Colors.METAL,
                scale=(1.5, 0.8, 1.5),
                position=position,
                rotation=(0, -angle, 0)
            )
            cubes.append(cube)

        self.decor_cubes = combine(cubes, name="decor_cubes")
        self.entities.append(self.decor_cubes)

    def create_domes(self):
        dome_configs = [
            (Vec3(1, 1, 0), Colors.DOME_RED),
            (Vec3(-1, 1, 0), Colors.DOME_GREEN),
            (Vec3(0, 1, 1), Colors.DOME_CYAN)
        ]

        self.domes = []
        self.warp_pads = []

        for dir_vec, dome_color in dome_configs:
            up_vec = dir_vec.normalized()
            position = up_vec * Physics.PLANET_RADIUS

            # Create dome
            dome = Entity(
                model='sphere',
                scale=8,
                color=dome_color,
                position=position
            )
            dome.look_at(position * 2)  # Orient away from center
            self.domes.append(dome)
            self.entities.append(dome)

            # Create warp pad
            warp_pad = Entity(
                model='cylinder',
                color=dome_color,
                scale=(3.6, 0.4, 3.6),
                position=position + up_vec * 0.2
            )
            warp_pad.look_at(position * 2)  # Orient same as dome
            self.warp_pads.append(warp_pad)
            self.entities.append(warp_pad)

    def create_central_star(self):
        self.central_star = Entity(
            model='sphere',
            color=Colors.STAR,
            scale=2,
            position=(0, Physics.PLANET_RADIUS + 8, 0),
            unlit=True
        )
        self.entities.append(self.central_star)
        self.animated_entities.append(self.central_star)

    def create_engine_room(self):
        engine_pos = Vec3(0, -(Physics.PLANET_RADIUS + 5), 0)

        # Base platform
        self.engine_base = Entity(
            model='cylinder',
            color=Colors.ENGINE,
            scale=(14, 0.8, 14),
            position=engine_pos
        )
        self.entities.append(self.engine_base)

        # Core
        self.engine_core = Entity(
            model='cylinder',
            color=Colors.METAL,
            scale=(3, 10, 3),
            position=engine_pos + Vec3(0, 5, 0)
        )
        self.entities.append(self.engine_core)

        # Supports
        supports = []
        for angle in range(0, 360, 60):
            support = Entity(
                model='cube',
                color=Colors.METAL,
                scale=(0.2, 1, 0.2),
                origin_y=-0.5,
                z=5 / 3,
                rotation_y=angle
            )
            supports.append(support)
        
        self.engine_supports = combine(supports, name="engine_supports")
        self.entities.append(self.engine_supports)

        # Energy nodes
        self.energy_nodes = []
        for i in range(5):
            theta = i * (2 * pi / 5)
            x = self.engine_base.scale_x/2 * cos(theta) + self.engine_base.x
            z = self.engine_base.scale_z/2 * sin(theta) + self.engine_base.z
            y = self.engine_base.y + 2
            node = Entity(model='sphere', color=Colors.ENERGY, scale=0.8, position=(x, y, z), unlit=True)
            self.energy_nodes.append(node)
            self.entities.append(node)
            self.animated_entities.append(node)

    def setup_lighting(self):
        DirectionalLight(direction=Vec3(1, -2, -1).normalized(), shadows=False, color=color.white * 0.2)
        AmbientLight(color=color.white * 0.4)

    def update_animations(self, t):
        self.central_star.scale = 2 + sin(t * 2) * 0.2
        self.central_star.rotation_y += time.dt * 10
        
        for i, node in enumerate(self.energy_nodes):
            node.scale = 0.8 + sin(t * 3 + i) * 0.15

class PerformanceMonitor:
    def __init__(self):
        self.fps_samples = []
        self.last_log_time = pytime.time()
        self.log_interval = 10

    def update(self):
        if time.dt > 0:
            self.fps_samples.append(1 / time.dt)
        current_time = pytime.time()
        if current_time - self.last_log_time >= self.log_interval:
            if self.fps_samples:
                avg_fps = sum(self.fps_samples) / len(self.fps_samples)
                min_fps = min(self.fps_samples)
                max_fps = max(self.fps_samples)
                print(f"[{pytime.strftime('%H:%M:%S')}] FPS Stats - Avg: {avg_fps:.1f}, Min: {min_fps:.1f}, Max: {max_fps:.1f}")
            self.fps_samples = []
            self.last_log_time = current_time

# Initialize game components
world = ObservatoryWorld()
player = SphericalPlayer(position=(0, Physics.PLANET_RADIUS + Physics.PLAYER_HEIGHT, 0))
performance_monitor = PerformanceMonitor()

# Global update function
def update():
    t = pytime.time()
    world.update_animations(t)
    performance_monitor.update()

# Input handling
def input(key):
    if key == 'escape': app.quit()
    elif key == 'space': player.jump()
    elif key == 'r': player.reset_position()
    elif key == 'f': window.fullscreen = not window.fullscreen
    elif key == 'tab':
        window.fps_counter.enabled = not window.fps_counter.enabled
        window.entity_counter.enabled = not window.entity_counter.enabled

# 🚀 Launch
if __name__ == '__main__':
    print("=== B3313 Engine - Comet Observatory ===")
    print("Controls:")
    print("  WASD - Move | Mouse - Look | Space - Jump | R - Reset")
    print("  F - Toggle Fullscreen | Tab - Toggle Perf Counters | ESC - Quit")
    print("\nEngine initialized. Performance stats logged every 10 seconds.")
    app.run()
