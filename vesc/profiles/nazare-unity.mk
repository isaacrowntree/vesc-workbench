# LaCroix Nazaré + FOCBOX Unity + DAVEGA X + Hoyt Puck
# Contributed by Isaac Rowntree
#
# ESC     FOCBOX Unity (single STM32, two motor threads over internal CAN)
# Firmware VESC 7.00 (hw target UNITY)
# Motors  dual 6389 190kv, hall sensored
# Drive   LaCroix Falcon gear drive, 4.2:1
# Wheels  8" / 200mm pneumatic on Hyper rims
# Battery 12s4p Sanyo NCR20700B (~17 Ah, 726 Wh) - confirmed
# Remote  Hoyt Puck (PPM, 3 modes)
# Display DAVEGA X firmware 5.06 (UART, 115200)

HOST  ?= 192.168.1.100   # phone running VESC Tool with the TCP bridge active
PORT  ?= 65102
CANID ?= 124             # second motor thread

# app_to_use MUST be 1 (PPM only) when running the DAVEGA shim: uart-start stops
# whatever app owns the UART pins, and "PPM and UART" is a single combined app,
# so choosing 4 takes the PPM decoder down with it and you lose throttle.
APP_TO_USE ?= 1

# Battery current: 30 A / -8 A per side (60 / -16 total), which is exactly
# what the 4P formula gives. This was originally set conservatively while the
# pack size was unconfirmed, on the reasoning that being wrong towards 4P was
# survivable and being wrong towards 6P was not. The pack turned out to be 4P,
# so the cautious number was also the correct one - no change needed.
#
#   battery max   = (parallel groups x 15) / 2     (dual motor, per ESC)
#   battery regen = (parallel groups x -4) / 2
#
# Motor current stays at 80 A/side; low-speed torque comes from there and is
# unaffected by pack configuration.
