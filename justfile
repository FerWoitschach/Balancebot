set shell := ["bash", "-cu"]

default:
  @printf "   ┬\n"
  @printf "   ╰─ \033[93mThere is no default rule!\033[0m\n\n"

  @just --list

containerfile := "containers/dev.containerfile"
image := "balancebot"

mcu    := "atmega328p"
device := "/dev/ttyACM0"
baud   := "57600"

python:
  uv venv --python 3.12 --prompt {{image}} .env/python
  source ./.env/python/bin/activate && uv pip install -r ./app/requirements.txt

build:
  sudo docker build --tag {{image}} --file {{containerfile}} .

compile:
  sudo docker run --rm --volume $(pwd):/workspace {{image}} avr-gcc -std=c11 -Os -DF_CPU=16000000UL -mmcu={{mcu}} app/source/main.c -o ./app/build/firmware.elf
  sudo docker run --rm --volume $(pwd):/workspace {{image}} avr-objcopy -O ihex -R .eeprom ./app/build/firmware.elf ./app/build/firmware.hex

flash port=device: compile
  sudo docker run --rm --device={{port}}:{{port}} -v $(pwd):/workspace {{image}} avrdude -F -v -p {{mcu}} -c arduino -P {{port}} -b 115200 -U flash:w:firmware.hex:i

monitor port=device:
  python3 -m serial.tools.miniterm /dev/ttyACM0 {{baud}}

shell port=device:
  sudo docker run --rm -it --device={{port}}:{{port}} -v $(pwd):/workspace {{image}} bash

clean:
  rm --force ./app/build/firmware.elf ./app/build/firmware.hex

simulate:
  python3 ./scripts/sim.py
