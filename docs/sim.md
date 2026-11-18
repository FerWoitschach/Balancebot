# Balancebot 3D Ultra-Realistic Simulator — Technical Documentation

## 1. System Architecture Overview
This simulator bridges embedded systems firmware with a 3D real-time graphical environment using **Ursina (Python)** and **simavr** (an AVR microcontroller simulator). 

The architecture relies on a **Hardware-In-The-Loop (HIL)** emulation pattern:
1. **Firmware Execution (`simavr`)**: Runs the compiled ATmega328P `.elf` binary in a background daemon thread.
2. **Inter-Process Communication (IPC)**: `simavr` prints debug telemetry (`PWM` and `Dir`) to `stdout`. The Python background thread captures and parses this stream asynchronously using Regular Expressions (`re`).
3. **Physics & Graphics Engine (`Ursina`)**: The main thread reads the latest PWM commands, processes advanced rigid-body dynamics, updates 3D transforms, renders shadows, and displays real-time telemetry HUD.

---

## 2. Physics Engine Details (Ultra-Realistic Inverted Pendulum)
Unlike the original crude approximation, the refactored physics engine implements a **Non-linear Inverted Pendulum on a Cart** model governed by Lagrangian mechanics:
* **Coupled Motion**: Wheel acceleration directly influences the chassis tilt angle ($\theta$), and body tilting creates horizontal reaction forces on the cart ($x$).
* **Sub-stepping Integration**: To ensure absolute numerical stability and prevent physics explosions, the simulation runs **10 sub-steps per frame**, utilizing refined Euler integration over delta time (`dt`).
* **Environmental Damping**: Includes angular damping, linear ground friction, and gravity ($g = 9.81 \text{ m/s}^2$).

---

## 3. Line-by-Line Code Breakdown

### Initialization & Window Setup
* `app = Ursina()`: Initializes the Ursina game engine context.
* `window.title`, `window.color`: Sets up a clean dark theme and custom window title.
* `EditorCamera`: Provides free 3D navigation for debugging angles and lighting.
* `DirectionalLight` & `AmbientLight`: Adds professional 3D shading, depth, and shadows.

### Robot Hierarchy & Entities
* `floor`: A large static plane serving as the driving surface with box collision.
* `chassis`: The primary parent entity representing the robot's body.
* `left_wheel` / `right_wheel`: Parented directly to `chassis`. As the chassis moves in 3D space, the wheels travel with it hierarchically while rotating independently along their local axis.
* `status_led`: A spherical indicator mounted on the front of the chassis that turns Green during stable operation ($\le 45^\circ$) and Red upon crashing.

### Firmware Emulation Thread (`run_simavr`)
* Checks if `firmware.elf` exists at `app/build/firmware.elf`.
* Spawns `simavr` via `subprocess.Popen` configuring an ATmega328P running at 16 MHz.
* Iterates over `sim_process.stdout` line-by-line, searching for regex matches (`PWM:(-?\d+)\s*\|\s*Dir:(\d+)`). Thread-safe locks (`sim_lock`) protect shared variables from race conditions.

### Physics & Update Loop (`update`)
* **Sub-stepping Loop**: Breaks down `time.dt` into 10 smaller intervals for smooth calculation.
* **Motor Force Calculation**: Converts PWM (0–255) into effective motor force, factoring in motor direction.
* **State Updates**: Computes angular acceleration ($\ddot{\theta}$) and cart acceleration ($\ddot{x}$), updating velocity and position state variables.
* **Transform Application**: Updates `chassis.x` (horizontal movement), `chassis.rotation_x` (tilt angle), and rolls `left_wheel` / `right_wheel` based on wheel circumference and linear velocity.
* **HUD Telemetry**: Renders live text on screen displaying PWM, Direction, Tilt Angle, Angular Velocity, Position X, and current FPS.

### User Interaction (`input`)
* `Spacebar`: Perturbs the robot by adding $+15^\circ$ of tilt to test the firmware's PID recovery loop.
* `R`: Resets the simulation state back to zero position.
* `Escape`: Terminates the `simavr` background process cleanly and exits the application.
