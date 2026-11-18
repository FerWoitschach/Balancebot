from ursina import *
import subprocess
import threading
import os
import re
import math
import random

app = Ursina()

window.title = "Balancebot 3D Realistic Simulator"
window.borderless = False
window.color = color.black
window.fps_counter.enabled = True
camera.clear_color = color.black

editor_camera = EditorCamera()
editor_camera.position = (0, 3, -14)
editor_camera.rotation = (15, 0, 0)

DirectionalLight(y=15, z=-8, shadows=True, color=color.rgb(255, 255, 255), rotation=(50, -45, 0))
AmbientLight(color=color.rgb(50, 50, 50))
PointLight(position=(0, 6, 0), color=color.rgb(100, 150, 255), range=25)

floor = Entity(model='plane', scale=(50, 1, 50), color=color.rgb(30, 30, 30), texture='white_cube', collider='box')
for i in range(-20, 21, 5):
    Entity(model='cube', scale=(50, 0.02, 0.1), position=(0, 0.01, i), color=color.rgb(60, 60, 60))
    Entity(model='cube', scale=(0.1, 0.02, 50), position=(i, 0.01, 0), color=color.rgb(60, 60, 60))

chassis = Entity(model='cube', color=color.gray, scale=(0.5, 1.3, 0.3), position=(0, 0.925, 0), collider='box')

battery_pack = Entity(parent=chassis, model='cube', color=color.rgb(40, 40, 40), scale=(0.45, 0.3, 0.28), position=(0, -0.3, 0))
mcu_board = Entity(parent=chassis, model='cube', color=color.rgb(0, 100, 50), scale=(0.4, 0.05, 0.25), position=(0, 0.1, 0))
imu_sensor = Entity(parent=chassis, model='cube', color=color.rgb(200, 150, 0), scale=(0.15, 0.02, 0.15), position=(0, 0.2, 0))

left_wheel = Entity(parent=chassis, model='cylinder', color=color.rgb(20, 20, 20), scale=(0.55, 0.08, 0.55), rotation=(0, 0, 90), position=(-0.35, -0.55, 0))
left_rim = Entity(parent=left_wheel, model='cylinder', color=color.rgb(180, 180, 180), scale=(0.6, 0.1, 0.6), rotation=(0, 0, 0))

right_wheel = Entity(parent=chassis, model='cylinder', color=color.rgb(20, 20, 20), scale=(0.55, 0.08, 0.55), rotation=(0, 0, 90), position=(0.35, -0.55, 0))
right_rim = Entity(parent=right_wheel, model='cylinder', color=color.rgb(180, 180, 180), scale=(0.6, 0.1, 0.6), rotation=(0, 0, 0))

status_led = Entity(parent=chassis, model='sphere', color=color.red, scale=0.12, position=(0, 0.55, -0.16))

hud_text = Text(text='', position=(-0.85, 0.48), scale=0.9, color=color.cyan)
controls_text = Text(
    text="[CONTROLS]\n"
         "• Click Tower: Apply Impact Strike\n"
         "• SPACE: Manual Push\n"
         "• R: Reset Simulation\n"
         "• ESC: Exit",
    position=(-0.85, -0.28), scale=0.75, color=color.light_gray
)

robot_angle = 0.0
robot_angular_velocity = 0.0
robot_position_x = 0.0
robot_velocity_x = 0.0

current_pwm = 0
current_dir = 0

elf_path = 'app/build/firmware.elf'
sim_process = None
sim_lock = threading.Lock()


def run_simavr():
    global sim_process, current_pwm, current_dir
    
    if not os.path.exists(elf_path):
        return

    try:
        sim_process = subprocess.Popen(
            ['simavr', '-m', 'atmega328p', '-f', '16000000', elf_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=0  # Sin buffering, lectura inmediata
        )
        
        for line in sim_process.stdout:
            match = re.search(r'AY:(-?\d+)\s*\|\s*PID:(-?\d+)\s*\|\s*Dir:(\d+)\s*\|\s*PWM:(-?\d+)', line)
            if match:
                with sim_lock:
                    current_dir = int(match.group(3))
                    current_pwm = int(match.group(4))
    except Exception:
        pass


sim_thread = threading.Thread(target=run_simavr, daemon=True)
sim_thread.start()


def update():
    global robot_angle, robot_angular_velocity, robot_position_x, robot_velocity_x, current_pwm, current_dir

    sub_steps = 10
    dt = time.dt / sub_steps
    if dt > 0.05:
        dt = 0.05 / sub_steps

    for _ in range(sub_steps):
        with sim_lock:
            pwm = current_pwm
            direction = current_dir

        if abs(robot_angle) >= 85.0:
            motor_force = 0.0
        else:
            motor_force = (pwm / 255.0) * 42.0
            if direction == 1:
                motor_force = -motor_force

        g = 9.81
        length = 0.65
        theta_rad = math.radians(robot_angle)
        sin_t = math.sin(theta_rad)
        cos_t = math.cos(theta_rad)

        angular_damping = 1.3 * robot_angular_velocity
        linear_damping = 2.2 * robot_velocity_x

        cart_acceleration = motor_force - linear_damping + (length * robot_angular_velocity**2 * sin_t)
        
        numerator = (g * sin_t) - (cos_t * (cart_acceleration * 0.1)) - (angular_damping * 0.05)
        denominator = length * (1.0 - 0.3 * cos_t**2)
        
        theta_ddot = numerator / denominator

        robot_angular_velocity += theta_ddot * dt
        robot_angle += math.degrees(robot_angular_velocity * dt)

        if robot_angle > 85.0:
            robot_angle = 85.0
            robot_angular_velocity = 0.0
        elif robot_angle < -85.0:
            robot_angle = -85.0
            robot_angular_velocity = 0.0

        robot_velocity_x += cart_acceleration * dt
        robot_position_x += robot_velocity_x * dt

    wheel_radius = 0.275
    length = 0.65
    theta_rad = math.radians(robot_angle)

    if sim_process and sim_process.poll() is None:
        try:
            # AY: Ángulo en centésimas de grado (ej. 15.5° -> 1550)
            # GY: Velocidad angular escalada para simular el giroscopio
            cmd = f"AY:{int(robot_angle * 100)}\nGY:{int(robot_angular_velocity * 65.5)}\n"
            sim_process.stdin.write(cmd)
            sim_process.stdin.flush()
        except Exception:
            pass
    
    chassis.x = robot_position_x + length * math.sin(theta_rad)
    chassis.y = wheel_radius + length * math.cos(theta_rad)
    chassis.rotation_x = robot_angle

    wheel_circumference = 2 * math.pi * wheel_radius
    wheel_rotation_speed = (robot_velocity_x / wheel_circumference) * 360 * time.dt * 12
    left_wheel.rotation_z += wheel_rotation_speed
    right_wheel.rotation_z += wheel_rotation_speed

    if abs(robot_angle) > 40.0:
        status_led.color = color.red
    else:
        status_led.color = color.green

    current_fps = int(1.0 / time.dt) if time.dt > 0 else 60
    hud_text.text = (
        f"=== BALANCEBOT TELEMETRY ===\n"
        f"PWM: {current_pwm} | Dir: {current_dir}\n"
        f"Tilt Angle: {robot_angle:6.2f}°\n"
        f"Angular Vel: {robot_angular_velocity:6.2f}°/s\n"
        f"Position X: {robot_position_x:6.2f}m\n"
        f"FPS: {current_fps}"
    )


def input(key):
    global robot_angle, robot_angular_velocity, robot_position_x, robot_velocity_x
    
    if key == 'left mouse down':
        if mouse.hovered_entity == chassis or (mouse.hovered_entity and mouse.hovered_entity.parent == chassis):
            if abs(robot_angle) < 85.0:
                strike_force = random.choice([-25.0, 25.0])
                robot_angular_velocity += strike_force

    if key == 'space':
        if abs(robot_angle) < 85.0:
            robot_angle += 15.0
    elif key == 'r':
        robot_angle = 0.0
        robot_angular_velocity = 0.0
        robot_position_x = 0.0
        robot_velocity_x = 0.0
    elif key == 'escape':
        if sim_process:
            sim_process.terminate()
        application.quit()


app.run()
