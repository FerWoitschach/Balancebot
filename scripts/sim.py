from ursina import *
import subprocess
import threading
import os
import re

app = Ursina()

window.title = "Self-Balancing Robot 3D Simulator"
window.borderless = False
window.color = color.dark_gray
window.fps_counter.enabled = True

editor_camera = EditorCamera()
editor_camera.position = (0, 2, -10)

piso = Entity(model='plane', scale=(20, 1, 20), color=color.gray, texture='white_cube')
rueda_izq = Entity(model='cylinder', color=color.black, scale=(0.6, 0.1, 0.6), rotation=(0, 0, 90), position=(-0.4, 0.3, 0))
rueda_der = Entity(model='cylinder', color=color.black, scale=(0.6, 0.1, 0.6), rotation=(0, 0, 90), position=(0.4, 0.3, 0))
chasis = Entity(model='cube', color=color.azure, scale=(0.6, 1.5, 0.3), position=(0, 1.0, 0))
led = Entity(model='sphere', color=color.red, scale=0.15, position=(0, 1.8, -0.16))

robot_angle = 0.0
robot_velocity = 0.0
current_pwm = 0
current_dir = 0

elf_path = 'firmware.elf'
sim_process = None

def run_simavr():
  global sim_process, current_pwm, current_dir
  if os.path.exists(elf_path):
    sim_process = subprocess.Popen(
      ['simavr', '-m', 'atmega328p', '-f', '16000000', elf_path],
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      text=True
    )
    for line in sim_process.stdout:
      match = re.search(r'PWM:(-?\d+)\s*\|\s*Dir:(\d+)', line)
      if match:
        current_pwm = int(match.group(1))
        current_dir = int(match.group(2))

sim_thread = threading.Thread(target=run_simavr, daemon=True)
sim_thread.start()

def update():
  global robot_angle, robot_velocity, current_pwm, current_dir

  motor_effect = (current_pwm / 255.0) * 20.0
  if current_dir == 1:
    motor_effect = -motor_effect

  gravity_torque = 15.0 * sin(math.radians(robot_angle))
  
  acceleration = gravity_torque + motor_effect - (robot_velocity * 0.8)
  robot_velocity += acceleration * time.dt
  robot_angle += robot_velocity * time.dt

  chasis.rotation_x = robot_angle
  rueda_izq.rotation_z += robot_velocity * 50 * time.dt
  rueda_der.rotation_z += robot_velocity * 50 * time.dt

  if abs(robot_angle) > 60:
    led.color = color.red
  else:
    led.color = color.green

def input(key):
  global robot_angle
  if key == 'space':
    robot_angle = 15.0
  if key == 'escape':
    if sim_process:
      sim_process.terminate()
    application.quit()

app.run()
