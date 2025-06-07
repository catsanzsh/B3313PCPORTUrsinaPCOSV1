"""
EZEngine - Comet Observatory Level
Combined build using EZEngine framework as base.
Single-file Python project: 1.py (Patched Build)
No external PNG dependencies; uses procedural geometry and mesh generation.
"""
from ursina import Ursina, Entity, camera, window, color, Vec3, Vec2, time, held_keys, mouse, clamp, DirectionalLight, AmbientLight
from ursina.mesh_importer import combine
# from ursina.prefabs.first_person_controller import FirstPersonController <- Replaced with custom controller
from ursina import Mesh
from math import sin, cos, pi, radians, sqrt, atan2, degrees
from functools import lru_cache
import random

# ----------------------
# Engine Bootstrap
# ----------------------
app = Ursina(
    vsync=True, # Set to True for smoother experience, False for max FPS
    development_mode=False,
    size=(1280,720),
    borderless=False,
    fullscreen=False
)
window.title = "EZEngine - Comet Observatory (Patched)"
window.color = color.rgb(8,10,22)
window.fps_counter.enabled = True
window.entity_counter.enabled = True
mouse.locked = True

# ----------------------
# Color Palette
# ----------------------
OBS_COLOR    = color.rgba(210,230,255,255)
ENGINE_COL   = color.rgba(90,90,160,240)
GLASS_COL    = color.rgba(160,220,255,120)
STAR_COLOR   = color.yellow
DOME_RED     = color.rgba(200,50,50)
DOME_GREEN   = color.rgba(50,150,50)
DOME_CYAN    = color.rgba(50,150,200)
METAL_COLOR  = color.rgba(100,100,100)
ENERGY_COLOR = color.rgba(100,150,255)

# ----------------------
# Physics & Planet
# ----------------------
GRAVITY      = 25
PLANET_CENTER= Vec3(0,0,0)
SURFACE_R    = 32
PLAYER_HEIGHT= 2
PLAYER_SPEED = 7
AIR_CONTROL  = 0.5
FRICTION     = 0.9

# ----------------------
# Utility: Low-poly sphere mesh generator
# ----------------------
@lru_cache(maxsize=1)
def create_lowpoly_sphere(segments=8):
    verts=[]; tris=[]
    for i in range(segments + 1):
        lat = pi * i / segments
        for j in range(segments + 1): # Use segments+1 to wrap texture coords correctly
            lon = 2 * pi * j / segments
            x = sin(lat) * cos(lon)
            y = cos(lat)
            z = sin(lat) * sin(lon)
            verts.append(Vec3(x, y, z))

    for i in range(segments):
        for j in range(segments):
            a = i * (segments + 1) + j
            b = a + 1
            c = (i + 1) * (segments + 1) + j
            d = c + 1
            tris.extend([(a, c, b), (b, c, d)])
    # The original function was missing normals and uvs, which can cause lighting issues.
    # We can let Ursina generate them.
    return Mesh(vertices=verts, triangles=tris, mode='triangle', static=True)

lowpoly_sphere = create_lowpoly_sphere(segments=12) # Increased segments for a rounder look

# ----------------------
# World Setup: Comet Observatory
# ----------------------
class ObservatoryWorld:
    def __init__(self):
        self.entities=[]
        self.animated=[]
        self.build()
    def build(self):
        # planet base
        floor = Entity(model=lowpoly_sphere, scale=SURFACE_R*2, color=OBS_COLOR, double_sided=True, collider='sphere')
        self.entities.append(floor)
        # decor cubes
        decor=[]
        for i in range(8):
            ang=i*(360/8)
            d=Vec3(cos(radians(ang)),0,sin(radians(ang)))
            e=Entity(model='cube', color=METAL_COLOR, scale=(1.5,0.8,1.5), position=d*(SURFACE_R-0.2), rotation=(0,ang,0))
            e.look_at(e.position * 2, up=e.position.normalized()) # Align to surface
            decor.append(e)
        combine(decor)
        # domes + warp pads
        for dir_vec, col in [(Vec3(1,1,0),DOME_RED),(Vec3(-1,1,0),DOME_GREEN),(Vec3(0,1,1),DOME_CYAN)]:
            up=dir_vec.normalized()
            pos=up*SURFACE_R
            dome=Entity(model=lowpoly_sphere, scale=8, color=col, position=pos)
            pad=Entity(model='cylinder', scale=(3.6,0.4,3.6), color=col, position=pos-up*0.2)
            dome.look_at(dome.position*2, up=up)
            pad.look_at(pad.position*2, up=up)
            self.entities+= [dome,pad]
        # central star
        star=Entity(model=lowpoly_sphere, scale=2, color=STAR_COLOR, position=(0,SURFACE_R+8,0), unlit=True)
        self.entities.append(star)
        self.animated.append(star)
        # engine room
        base_pos = Vec3(0,-(SURFACE_R+5),0)
        base=Entity(model='cylinder', color=ENGINE_COL, scale=(14,0.8,14), position=base_pos)
        core=Entity(model='cylinder', color=METAL_COLOR, scale=(3,10,3), position=base_pos + Vec3(0,5,0))
        self.entities+=[base,core]
        supports=[]
        for ang in range(0,360,60):
            s=Entity(model='cube', color=METAL_COLOR, scale=(0.6,10.2,0.6), position=core.position, rotation=(0,ang,0))
            supports.append(s)
        combine(supports)
        # energy nodes
        self.nodes=[]
        for i in range(5):
            th=i*(2*pi/5)
            x=7*cos(th); z=7*sin(th)
            node=Entity(model=lowpoly_sphere, color=ENERGY_COLOR, unlit=True, scale=0.8, position=(x,base_pos.y+2,z))
            self.nodes.append(node)
            self.entities.append(node)
        # lighting
        DirectionalLight(direction=Vec3(1,-2,-1).normalized(), shadows=False, color=color.rgba(255,255,255,0.3))
        AmbientLight(color=color.rgba(100,100,120,0.7))

world = ObservatoryWorld()

# ----------------------------------------------------
# Player Controller: Spherical gravity (Corrected)
# ----------------------------------------------------
class SphericalController(Entity):
    def __init__(self, **kwargs):
        super().__init__(origin_y=-0.5, **kwargs) # Set origin to feet
        self.height = PLAYER_HEIGHT
        self.camera_pivot = Entity(parent=self, y=self.height)

        camera.parent = self.camera_pivot
        camera.position = (0,0,0)
        camera.rotation = (0,0,0)
        camera.fov = 90
        
        self.velocity = Vec3(0,0,0)
        self.grounded = True
        self.jump_height = 8.0
        self.speed = PLAYER_SPEED
        self.mouse_sensitivity = Vec2(40, 40)

    def update(self):
        # 1. Align player's rotation to the planet's surface normal
        self.up = (self.position - PLANET_CENTER).normalized()
        self.rotation_y += mouse.velocity[0] * self.mouse_sensitivity[1]
        self.look_at(self.position + self.forward, up=self.up)
        
        # 2. Camera look up/down
        self.camera_pivot.rotation_x -= mouse.velocity[1] * self.mouse_sensitivity[0]
        self.camera_pivot.rotation_x = clamp(self.camera_pivot.rotation_x, -90, 90)

        # 3. Movement
        move_input = (self.forward * (held_keys['w'] - held_keys['s']) +
                      self.right * (held_keys['d'] - held_keys['a']))
        
        # Project movement input onto the current ground plane
        move_direction = move_input - self.up * move_input.dot(self.up)
        if move_direction.length() > 0:
            move_direction.normalize()

        if self.grounded:
            # On the ground, directly influence velocity for a responsive feel
            target_velocity = move_direction * self.speed
            # Interpolate towards target velocity
            self.velocity = self.velocity * 0.8 + target_velocity * 0.2
            # Apply friction when no keys are pressed
            if not any(held_keys.values()):
                self.velocity *= FRICTION
        else:
            # In the air, apply a smaller force
            self.velocity += move_direction * self.speed * AIR_CONTROL * time.dt

        # 4. Gravity
        self.velocity += -self.up * GRAVITY * time.dt

        # 5. Apply final velocity
        self.position += self.velocity * time.dt
        
        # 6. Ground collision and snapping
        dist_from_center = self.position.length()
        if dist_from_center <= SURFACE_R:
            self.grounded = True
            self.position = self.position.normalized() * SURFACE_R
            
            # Remove any velocity component pointing into the ground
            radial_v = self.velocity.dot(self.up)
            if radial_v < 0:
                self.velocity -= self.up * radial_v
        else:
            self.grounded = False

    def input(self, key):
        if key == 'space':
            self.jump()

    def jump(self):
        if self.grounded:
            self.velocity += self.up * self.jump_height
            self.grounded = False

# Player must be invisible so we don't see our own model
player = SphericalController(visible=False)
player.position=(0,SURFACE_R,0)

# ----------------------
# Animation & Stars
# ----------------------
stars=[]
# Use a starfield Entity for performance instead of drawing dots every frame
starfield = Entity()
star_mesh = Mesh(mode='point', thickness=.05)
for i in range(500):
    pos = Vec3(random.uniform(-1,1),random.uniform(-1,1),random.uniform(-1,1)).normalized() * 100
    star_mesh.vertices.append(pos)
    star_mesh.colors.append(color.white)
starfield.model = star_mesh


# update loop
pulse=0
node_offsets=[random.random() for _ in world.nodes]
def update():
    global pulse
    t=time.time()
    
    # Central star pulse
    pulse=sin(t*2)*0.2
    world.animated[0].scale = 2 + pulse
    
    # Energy nodes pulse
    for i,node in enumerate(world.nodes):
        node.scale=0.8 + sin(t*3 + node_offsets[i])*0.15
        
    # Rotate starfield for a dynamic background
    starfield.rotation_y += time.dt * 0.1
    starfield.rotation_x += time.dt * 0.05


# ----------------------
# Launch
# ----------------------
print("EZEngine Comet Observatory - Use WASD + Mouse. Jump: Space.")
app.run()
