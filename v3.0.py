from ursina import (
    Ursina, Entity, camera, window, color, held_keys, mouse, time, clamp,
    Vec2, Vec3,
    Mesh, DirectionalLight, AmbientLight,
    Sky, destroy
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
        self.start_pos = Vec3(self.position)  # Fixed: Use Vec3() instead of copy()

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

        # Update rotation (yaw)
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity.x * time.dt

        # Camera pitch
        self.camera_pivot.rotation_x = clamp(
            self.camera_pivot.rotation_x - mouse.velocity[1] * self.mouse_sensitivity.y * time.dt,
            -90, 90
        )

        # Movement input
        move_x = held_keys['d'] - held_keys['a']
        move_z = held_keys['w'] - held_keys['s']

        # Project camera directions onto tangent plane
        camera_forward = camera.forward
        camera_right = camera.right
        tangent_forward = (camera_forward - surface_normal * surface_normal.dot(camera_forward)).normalized()
        tangent_right = (camera_right - surface_normal * surface_normal.dot(camera_right)).normalized()

        # Calculate movement
        if move_x != 0 or move_z != 0:
            move_direction = (tangent_forward * move_z + tangent_right * move_x).normalized()
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
            radial_velocity = self.velocity.dot(surface_normal)
            if radial_velocity < 0:
                self.velocity -= surface_normal * radial_velocity
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
        self.position = Vec3(self.start_pos)  # Fixed: Use Vec3() instead of copy()
        self.velocity = Vec3(0, 0, 0)
        self.rotation = Vec3(0, 0, 0)
        self.camera_pivot.rotation_x = 0
        print("Player reset to starting position")

class ObservatoryWorld:
    def __init__(self):
        self.entities = []
        self.animated_entities = []
        self.warp_pads = []
        self.create_world()

    def create_world(self):
        Sky(texture='sky_default', color=color.white * 0.8)
        self.main_floor = Entity(
            model='sphere',
            scale=Physics.PLANET_RADIUS * 2,
            color=Colors.OBSERVATORY
        )
        self.entities.append(self.main_floor)
        self.create_decorative_cubes()
        self.create_domes()
        self.create_central_star()
        self.create_engine_room()
        self.setup_lighting()

    def create_decorative_cubes(self):
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
                parent=self.main_floor
            )

    def create_domes(self):
        dome_configs = [
            (Vec3(1, 1, 0), Colors.DOME_RED),
            (Vec3(-1, 1, 0), Colors.DOME_GREEN),
            (Vec3(0, 1, 1), Colors.DOME_CYAN)
        ]
        self.domes = []
        for dir_vec, dome_color in dome_configs:
            up_vec = dir_vec.normalized()
            position = up_vec * Physics.PLANET_RADIUS
            dome = Entity(
                model='sphere',
                scale=8,
                color=dome_color,
                position=position
            )
            dome.rotation_x = -degrees(atan2(up_vec.z, up_vec.y))
            dome.rotation_y = degrees(atan2(up_vec.x, up_vec.z))
            self.domes.append(dome)
            self.entities.append(dome)

            warp_pad = Entity(
                model='cylinder',
                color=dome_color,
                scale=(3.6, 0.4, 3.6),
                position=position + up_vec * 0.2,
                rotation=(dome.rotation_x, dome.rotation_y, 0),
                collider=None
            )
            self.warp_pads.append(warp_pad)
            self.entities.append(warp_pad)

    def create_central_star(self):
        self.central_star = Entity(
            model='sphere',
            subdivisions=2,
            color=Colors.STAR,
            scale=2,
            position=(0, Physics.PLANET_RADIUS + 8, 0),
            collider='sphere'
        )
        self.entities.append(self.central_star)
        self.animated_entities.append(self.central_star)

    def create_engine_room(self):
        engine_pos = Vec3(0, -(Physics.PLANET_RADIUS + 5), 0)
        self.engine_base = Entity(
            model='cylinder',
            color=Colors.ENGINE,
            scale=(14, 0.8, 14),
            position=engine_pos,
            collider=None
        )
        self.entities.append(self.engine_base)

        self.engine_core = Entity(
            model='cylinder',
            color=Colors.METAL,
            scale=(3, 10, 3),
            position=engine_pos + Vec3(0, 5, 0),
            collider=None
        )
        self.entities.append(self.engine_core)

        supports = []
        for angle in range(0, 360, 60):
            support = Entity(
                model='cube',
                color=Colors.METAL,
                scale=(0.6, 10, 0.6),
                position=self.engine_core.position,
                rotation=(0, angle, 0),
                collider=None
            )
            support.origin_y = -0.5
            support.z = -5
            supports.append(support)
        self.engine_supports = Entity(model=Mesh(vertices=sum([e.get_vertices() for e in supports], []), mode='triangle'), color=Colors.METAL)
        self.entities.append(self.engine_supports)
        for support in supports:
            destroy(support)

        self.energy_nodes = []
        for i in range(5):
            theta = i * (2 * pi / 5)
            x = self.engine_base.scale_x/2 * cos(theta) + self.engine_base.x
            z = self.engine_base.scale_z/2 * sin(theta) + self.engine_base.z
            y = self.engine_base.y + 2
            node = Entity(
                model='sphere',
                subdivisions=1,
                color=Colors.ENERGY,
                scale=0.8,
                position=(x, y, z),
                collider=None
            )
            self.energy_nodes.append(node)
            self.entities.append(node)
            self.animated_entities.append(node)

    def setup_lighting(self):
        DirectionalLight(
            direction=Vec3(1, -2, -1).normalized(),
            shadows=False,
            color=color.rgba(255, 255, 255, 0.2)
        )
        AmbientLight(color=color.rgba(100, 100, 100, 255)) 
