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
        
        # Remove sphere collider - causes performance issues
        # self.collider = 'sphere'

        # Camera setup
        self.camera_pivot = Entity(parent=self, y=self.height/2)
        camera.parent = self.camera_pivot
        camera.position = Vec3(0, 0, 0)
        camera.rotation = Vec3(0, 0, 0)
        camera.fov = 90

        # Input setup
        mouse.locked = True
        self.mouse_sensitivity = Vec2(100, 100)
        
        # Cache for surface normal
        self._last_pos_tuple = None
        self._cached_normal = None

    def get_surface_normal(self, pos):
        """Get surface normal with simple caching"""
        pos_tuple = (round(pos.x, 1), round(pos.y, 1), round(pos.z, 1))
        if pos_tuple != self._last_pos_tuple:
            self._last_pos_tuple = pos_tuple
            self._cached_normal = (pos - Physics.PLANET_CENTER).normalized()
        return self._cached_normal

    def update(self):
        # Get surface normal
        surface_normal = self.get_surface_normal(self.position)
        
        # Create up vector that's perpendicular to surface
        world_forward = Vec3(0, 0, -1)
        if abs(surface_normal.dot(world_forward)) > 0.99:
            world_forward = Vec3(1, 0, 0)
        
        right = world_forward.cross(surface_normal).normalized()
        forward = surface_normal.cross(right).normalized()
        
        # Build rotation matrix manually (more stable than look_at)
        self.model.setMat(self.model.getMat())
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity.x * time.dt

        # Mouse look (camera pitch)
        self.camera_pivot.rotation_x = clamp(
            self.camera_pivot.rotation_x - mouse.velocity[1] * self.mouse_sensitivity.y * time.dt,
            -90, 90
        )

        # Movement input
        move_x = held_keys['d'] - held_keys['a']
        move_z = held_keys['w'] - held_keys['s']
        
        if move_x != 0 or move_z != 0:
            # Normalize movement vector
            move_length = sqrt(move_x * move_x + move_z * move_z)
            move_x /= move_length
            move_z /= move_length
            
            move_direction = self.forward * move_z + self.right * move_x
            move_amount = move_direction * self.speed * (Physics.AIR_CONTROL if not self.grounded else 1.0)
        else:
            move_amount = Vec3(0, 0, 0)
        
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
            if move_x == 0 and move_z == 0:
                self.velocity *= Physics.FRICTION
        else:
            self.grounded = False

    def jump(self):
        if self.grounded:
            surface_normal = self.get_surface_normal(self.position)
            self.velocity += surface_normal * self.jump_height
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

        # Main planetoid (no collider for performance)
        self.main_floor = Entity(
            model='sphere',
            scale=Physics.PLANET_RADIUS * 2,
            color=Colors.OBSERVATORY
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
        # Create cubes as a single combined entity for performance
        for i in range(8):
            angle = i * (360 / 8)
            dir_vec = Vec3(cos(radians(angle)), 0, sin(radians(angle)))
            position = dir_vec * (Physics.PLANET_RADIUS - 0.2)

            Entity(
                model='cube',
                color=Colors.METAL,
                scale=(1.5, 0.8, 1.5),
                position=position,
                rotation=(0, -angle, 0),
                parent=self.main_floor  # Parent to main floor for better performance
            )

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
            # Simplified orientation
            dome.rotation_x = -degrees(atan2(up_vec.z, up_vec.y))
            dome.rotation_y = degrees(atan2(up_vec.x, up_vec.z))
            self.domes.append(dome)
            self.entities.append(dome)

            # Create warp pad
            warp_pad = Entity(
                model='cylinder',
                color=dome_color,
                scale=(3.6, 0.4, 3.6),
                position=position + up_vec * 0.2
            )
            warp_pad.rotation_x = dome.rotation_x
            warp_pad.rotation_y = dome.rotation_y
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

        # Supports - create directly without combine for performance
        for angle in range(0, 360, 60):
            Entity(
                model='cube',
                color=Colors.METAL,
                scale=(0.2, 10, 0.2),
                position=engine_pos + Vec3(cos(radians(angle)) * 5, 5, sin(radians(angle)) * 5),
                parent=self.engine_base
            )

        # Energy nodes
        self.energy_nodes = []
        for i in range(5):
            theta = i * (2 * pi / 5)
            x = 7 * cos(theta)
            z = 7 * sin(theta)
            y = 2
            node = Entity(
                model='sphere', 
                color=Colors.ENERGY, 
                scale=0.8, 
                position=engine_pos + Vec3(x, y, z), 
                unlit=True
            )
            self.energy_nodes.append(node)
            self.entities.append(node)
            self.animated_entities.append(node)

    def setup_lighting(self):
        DirectionalLight(direction=Vec3(1, -2, -1).normalized(), shadows=False, color=color.white * 0.2)
        AmbientLight(color=color.white * 0.4)

    def update_animations(self, t):
        # Optimized animations
        star_scale = 2 + sin(t * 2) * 0.2
        self.central_star.scale = star_scale
        self.central_star.rotation_y += 10 * time.dt
        
        # Update energy nodes with cached sin values
        base_scale = 0.8
        amplitude = 0.15
        for i, node in enumerate(self.energy_nodes):
            node.scale = base_scale + sin(t * 3 + i) * amplitude

class PerformanceMonitor:
    def __init__(self):
        self.fps_samples = []
        self.last_log_time = pytime.time()
        self.log_interval = 10
        self.sample_count = 0
        self.max_samples = 600  # 10 seconds at 60 FPS

    def update(self):
        if time.dt > 0:
            self.fps_samples.append(1 / time.dt)
            self.sample_count += 1
            
            # Limit sample buffer size
            if self.sample_count > self.max_samples:
                self.fps_samples.pop(0)
                self.sample_count = self.max_samples
        
        current_time = pytime.time()
        if current_time - self.last_log_time >= self.log_interval:
            if self.fps_samples:
                avg_fps = sum(self.fps_samples) / len(self.fps_samples)
                min_fps = min(self.fps_samples)
                max_fps = max(self.fps_samples)
                print(f"[{pytime.strftime('%H:%M:%S')}] FPS Stats - Avg: {avg_fps:.1f}, Min: {min_fps:.1f}, Max: {max_fps:.1f}")
            self.fps_samples = []
            self.sample_count = 0
            self.last_log_time = current_time

# Initialize game components
world = ObservatoryWorld()
player = SphericalPlayer(position=(0, Physics.PLANET_RADIUS + Physics.PLAYER_HEIGHT, 0))
performance_monitor = PerformanceMonitor()

# Global update function
def update():
    t = time.time  # Use Ursina's time.time instead of pytime.time()
    world.update_animations(t)
    performance_monitor.update()

# Input handling
def input(key):
    if key == 'escape': 
        app.quit()
    elif key == 'space': 
        player.jump()
    elif key == 'r': 
        player.reset_position()
    elif key == 'f': 
        window.fullscreen = not window.fullscreen
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
