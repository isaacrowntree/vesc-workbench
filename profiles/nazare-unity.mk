# LaCroix Nazaré + FOCBOX Unity + DAVEGA X + Hoyt Puck
# Contributed by Isaac Rowntree
#
# ESC     FOCBOX Unity (single STM32, two motor threads over internal CAN)
# Firmware VESC 7.00 (hw target UNITY)
# Motors  dual 6389 190kv, hall sensored
# Drive   LaCroix Falcon gear drive, 4.2:1
# Wheels  8" / 200mm pneumatic on Hyper rims
# Battery 12s6p Sanyo NCR20700B (~25.5 Ah, 1089 Wh)
# Remote  Hoyt Puck (PPM, 3 modes)
# Display DAVEGA X firmware 5.06 (UART, 115200)

HOST  ?= 192.168.1.100   # phone running VESC Tool with the TCP bridge active
PORT  ?= 65102
CANID ?= 124             # second motor thread

# app_to_use MUST be 1 (PPM only) when running the DAVEGA shim: uart-start stops
# whatever app owns the UART pins, and "PPM and UART" is a single combined app,
# so choosing 4 takes the PPM decoder down with it and you lose throttle.
APP_TO_USE ?= 1

# Battery current is deliberately conservative: 30 A / -8 A per side (60 / -16
# total) rather than the 45 / -12 the 12s6p formula gives, because the pack size
# is not confirmed from a label. If it is 6P, 45 A/side is exactly at cell spec
# and 30 costs only top-end power. If it is 4P, 45 A/side is ~22.5 A per cell
# against a ~15 A rated cell. Low-speed torque is unaffected either way - that
# comes from motor current, which stays at 80 A/side.
#
#   battery max   = (parallel groups x 15) / 2     (dual motor, per ESC)
#   battery regen = (parallel groups x -4) / 2
