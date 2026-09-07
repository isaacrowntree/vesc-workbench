# LaCroix Unity / DAVEGA workbench.
#
# Everything talks to the board over the phone's TCP bridge:
#   phone VESC Tool -> BLE -> Unity, Start page -> "Wireless Bridge to Computer (TCP)"
# Desktop VESC Tool must be CLOSED - the bridge accepts one client.
#
#   make help

# Load a board profile if one is given: make davega-debug PROFILE=vesc/profiles/nazare-unity.mk
PROFILE ?=
ifneq ($(PROFILE),)
include $(PROFILE)
endif

HOST    ?= 192.168.1.100
PORT    ?= 65102
CANID   ?= 124
# VESC Tool binary. Override on Linux, e.g. VESC=/opt/vesc_tool/vesc_tool
UNAME   := $(shell uname -s)
ifeq ($(UNAME),Darwin)
VESC    ?= /Applications/VESC Tool.app/Contents/MacOS/VESC Tool
VESCPROC ?= VESC Tool
else
VESC    ?= vesc_tool
VESCPROC ?= vesc_tool
endif
CONFDIR ?= $(ROOT)/configs
OUTDIR  ?= $(ROOT)/backups/qml-pull
LISP    ?= lisp/src/davega_shim.lisp
TIMEOUT ?= 120
SECS    ?= 15

BUILD := build
ROOT  := $(shell pwd)

.PHONY: help test test-py test-lisp check bridge probe pull apply upload-lisp \
        upload-hello lisp-stop lisp-stats clean

help:
	@echo "Board (over the TCP bridge at $(HOST):$(PORT)):"
	@echo "  make check         - is the bridge up and the desktop app closed?"
	@echo "  make probe         - connect, report firmware + LispBM stats"
	@echo "  make pull          - read both sides' configs -> backups/qml-pull/"
	@echo "  make apply         - write motor configs to both sides"
	@echo "  make apply-appconf - write local app config (app_to_use)"
	@echo "  make motors-off    - disable motor output (bench work), keeps DAVEGA live"
	@echo "  make motors-on     - re-enable motor output"
	@echo "  make lisp-erase    - erase LispBM + reboot (restores stock PPM/UART behaviour)"
	@echo "  make reboot        - stop LispBM and reboot the ESC (restarts the PPM app)"
	@echo "  make faults        - stored fault history + live values, both sides"
	@echo "  make logger        - upload the flight recorder (replaces the proxy)"
	@echo "  make log-pull      - print the ride summary it recorded"
	@echo "  make ppm-watch     - continuous PPM readout, prints only on change"
	@echo "  make ppm-cal       - live Hoyt Puck calibration (follow the prompts)"
	@echo "  make upload-hello  - upload+run the minimal LispBM smoke test"
	@echo "  make upload-lisp   - upload+run LISP=$(LISP)"
	@echo "  make davega-debug  - DAVEGA proxy health check with a verdict"
	@echo "  make lisp-stats    - LispBM heap/cpu stats"
	@echo "  make lisp-stop     - stop the running LispBM script"
	@echo ""
	@echo "DAVEGA X display (its own WiFi AP, not the board):"
	@echo "  make mockups        - render every screen to an HTML page"
	@echo "  make webrepl        - fetch the WebREPL client and open it locally"
	@echo "  make davega-recon   - read-only device recon over WebREPL"
	@echo "  make davega-settings- print /config.json"
	@echo "  make davega-gate    - inspect the version gate in frozen.run_standard"
	@echo "  make davega-theme THEME=nazare - choose a dash theme"
	@echo "  make davega-display MODE=day|night - light or dark variant"
	@echo "  (the three above need WEBREPL_PASSWORD=xxxx and this machine on its AP)"
	@echo ""
	@echo "Offline:"
	@echo "  make test          - all host-side tests"
	@echo "  make test-py       - shim reference + payload layout tests"
	@echo "  make gui-test      - DAVEGA screen tests: golden images, budget, sweeps"
	@echo "  make test-device   - the dashboard end to end in real MicroPython (docker)"
	@echo "  make test-lisp     - run the LispBM logic in the upstream REPL (Docker)"
	@echo ""
	@echo "Vars: HOST=$(HOST) PORT=$(PORT) CANID=$(CANID) SECS=$(SECS)"
	@echo "      PROFILE=$(PROFILE)   (e.g. vesc/profiles/nazare-unity.mk)"

# ---- offline tests ---------------------------------------------------------
test: test-py gui-test test-lisp test-device

test-py:
	@cd lisp/model && python3 test_shim.py && python3 test_layout.py

# Every suite runs even when an earlier one fails. Stopping at the first
# failure hid a real layout bug behind an unrelated one for an entire session.
gui-test:
	@fail=0; for t in screens themes ui vesc input runner session boot; do \
	  python3 davega/tests/test_$$t.py || fail=1; \
	done; \
	if [ $$fail -ne 0 ]; then echo "SOME GUI SUITES FAILED"; exit 1; fi

gui-golden:
	@python3 davega/tests/test_screens.py --update-golden

test-lisp:
	@./lisp/tests/run-lisp-tests.sh

# ---- board ------------------------------------------------------------------
check:
	@nc -z -w 3 $(HOST) $(PORT) >/dev/null 2>&1 \
	  && echo "bridge $(HOST):$(PORT) OPEN" \
	  || { echo "bridge $(HOST):$(PORT) UNREACHABLE - activate it on the phone"; exit 1; }
	@pgrep -x "$(VESCPROC)" >/dev/null \
	  && { echo "desktop VESC Tool is RUNNING - close it, the bridge takes one client"; exit 1; } \
	  || echo "desktop VESC Tool closed - ok"

$(BUILD):
	@mkdir -p $(BUILD)

# render a .qml template with the current settings
define render
	@mkdir -p $(BUILD)
	@sed -e 's|@@HOST@@|$(HOST)|g' -e 's|@@PORT@@|$(PORT)|g' \
	     -e 's|@@CANID@@|$(CANID)|g' -e 's|@@SECS@@|$(SECS)|g' -e 's|@@CONFDIR@@|$(CONFDIR)|g' -e 's|@@OUTDIR@@|$(OUTDIR)|g' -e 's|@@LISP@@|$(ROOT)/$(LISP)|g' \
	     vesc/qml/$(1).qml > $(BUILD)/$(1).qml
endef

# run a rendered template, filtering the noise Qt prints on teardown
define run_qml
	@$(call render,$(1)) \
	; ( "$(VESC)" --offscreen --loadQml $(BUILD)/$(1).qml & p=$$!; \
	    ( sleep $(TIMEOUT); kill -9 $$p 2>/dev/null ) >/dev/null 2>&1 & w=$$!; \
	    wait $$p 2>/dev/null; kill $$w 2>/dev/null ) 2>&1 \
	  | grep -vE 'getAppHexColor|Loaded config resource|Implicitly defined'
endef

probe: check
	$(call run_qml,lisp-probe)

pull: check
	$(call run_qml,pull-configs)
	@echo "--- pulled:"; ls -1 backups/qml-pull/ 2>/dev/null

apply: check
	@echo "writing configs-to-load/ to both sides"
	$(call run_qml,apply-configs)

# Build the minified proxy variants from source. Without these rules the
# motors-off/motors-on targets uploaded files nothing created - and an empty
# file makes lisp-upload.qml abort while make still reported success, i.e.
# "motors disabled" printed with the motors still live.
.SECONDARY: build/davega_proxy_live.lisp build/davega_proxy_safe.lisp build/davega_logger.lisp

# The proxy variants differ only in their output policy, so they are assembled
# from the shared core rather than kept as two near-identical copies.
build/davega_logger.lisp: lisp/src/logger.lisp lisp/src/logger-main.lisp
	@mkdir -p $(BUILD)
	@cat $^ > $@

build/logger.min.lisp: build/davega_logger.lisp lisp/minify.py
	@mkdir -p $(BUILD)
	@python3 lisp/minify.py $< $@ $(CANID)

# Flight recorder. Replaces the DAVEGA proxy - one LispBM script at a time.
logger: check build/logger.min.lisp
	@echo "uploading the flight recorder (this REPLACES the DAVEGA proxy)"
	@$(MAKE) --no-print-directory upload-lisp LISP=build/logger.min.lisp

log-pull: check
	$(call run_qml,log-pull)

build/davega_proxy_%.lisp: lisp/src/proxy.lisp lisp/src/reader.lisp lisp/src/proxy-main.lisp lisp/src/output-%.lisp
	@mkdir -p $(BUILD)
	@cat $^ > $@

build/proxy_%.min.lisp: build/davega_proxy_%.lisp lisp/minify.py
	@mkdir -p $(BUILD)
	@python3 lisp/minify.py $< $@ $(CANID)

build/davega_shim.min.lisp: lisp/src/davega_shim.lisp lisp/minify.py
	@mkdir -p $(BUILD)
	@python3 lisp/minify.py $< $@ $(CANID)

motors-off: check build/proxy_safe.min.lisp
	@echo "uploading proxy with motor output DISABLED (bench mode)"
	@$(MAKE) --no-print-directory upload-lisp LISP=build/proxy_safe.min.lisp

motors-on: check build/proxy_live.min.lisp
	@echo "uploading proxy with motor output ENABLED"
	@$(MAKE) --no-print-directory upload-lisp LISP=build/proxy_live.min.lisp

davega-debug: check
	$(call run_qml,davega-debug)

enum-dump: check
	$(call run_qml,enum-dump)

lisp-erase: check
	@echo "erasing LispBM and rebooting"
	$(call run_qml,lisp-erase)

reboot: check
	$(call run_qml,reboot)

# The DAVEGA's access point has no internet, so the WebREPL client has to be
# on disk before you join it. Fetch it first, then open it from file://.
WEBREPL := $(BUILD)/webrepl-master/webrepl.html

$(WEBREPL):
	@mkdir -p $(BUILD)
	@echo "fetching the WebREPL client..."
	@curl -sL -o $(BUILD)/webrepl.zip https://github.com/micropython/webrepl/archive/refs/heads/master.zip
	@unzip -oq $(BUILD)/webrepl.zip -d $(BUILD)

# Drive the display's REPL from the shell instead of the browser terminal.
# Needs this machine joined to the DAVEGA's AP, and its WebREPL password:
#   make davega-recon WEBREPL_PASSWORD=xxxx
DAVEGA_HOST ?= 192.168.4.1
# The display's WebREPL password. Not a secret - the vendor publishes it on
# davega.eu/sn8ke ("davega" reversed). Override if you have changed it.
WEBREPL_PASSWORD ?= agevad
export WEBREPL_PASSWORD

davega-recon:
	@python3 davega/tools/webrepl-run.py --host $(DAVEGA_HOST) \
	  -f davega/tools/recon.py -e "recon()"

davega-settings:
	@python3 davega/tools/webrepl-run.py --host $(DAVEGA_HOST) \
	  -f davega/tools/settings.py -e "show()"

# Select a davega theme. Names come from davega/gui/themes.py.
davega-theme:
	@test -n "$(THEME)" || { echo "usage: make davega-theme THEME=nazare"; exit 1; }
	@python3 davega/tools/webrepl-run.py --host $(DAVEGA_HOST) \
	  -f davega/tools/settings.py -e "set_theme('$(THEME)')"

# Day or night, for whichever theme is selected.
davega-display:
	@test -n "$(MODE)" || { echo "usage: make davega-display MODE=day|night"; exit 1; }
	@python3 davega/tools/webrepl-run.py --host $(DAVEGA_HOST) \
	  -f davega/tools/settings.py -e "set_display('$(MODE)')"

davega-gate:
	@python3 davega/tools/webrepl-run.py --host $(DAVEGA_HOST) \
	  -f davega/tools/recon.py -e "probe('frozen.run_standard')"

# Push the dashboard to the display, as bytecode.
#
# MicroPython compiles a .py every single time it imports it, and on this
# ESP32 that compile is most of the wait between switching the board on and
# seeing a number. mpy-cross does it once, here: 162 kB of source becomes
# 60 kB of bytecode with no compile step left to run on the device.
#
# mpy v5 is what MicroPython 1.14 loads (sys.implementation.mpy == 10757), and
# mpy-cross 1.12 is the newest release on PyPI that still emits it.
MPY_VERSION ?= 1.12
MPY_VENV := build/mpy-venv
MPY_CROSS := $(MPY_VENV)/bin/mpy-cross-bin
MODULES ?= $(basename $(notdir $(wildcard davega/gui/*.py)))
LAYOUTS ?= $(basename $(notdir $(wildcard davega/gui/layouts/*.py)))

$(MPY_CROSS):
	@echo "fetching mpy-cross $(MPY_VERSION) (emits the mpy v5 the display loads)"
	@python3 -m venv $(MPY_VENV)
	@$(MPY_VENV)/bin/pip install --quiet 'mpy-cross==$(MPY_VERSION)'
	@ln -sf "$$($(MPY_VENV)/bin/python -c 'import mpy_cross;print(mpy_cross.mpy_cross)')" $(MPY_CROSS)

# Compile everything that ships. `start.py` is deliberately absent: it is the
# escape hatch, and an escape hatch that depends on the toolchain having run
# is not one.
mpy: $(MPY_CROSS)
	@rm -rf build/mpy && mkdir -p build/mpy/layouts
	@for f in davega/gui/*.py davega/gui/runner.py davega/gui/boot.py; do \
	  $(MPY_CROSS) -o build/mpy/`basename $$f .py`.mpy $$f || exit 1; done
	@for f in davega/gui/layouts/*.py; do \
	  $(MPY_CROSS) -o build/mpy/layouts/`basename $$f .py`.mpy $$f || exit 1; done
	@echo "compiled `ls build/mpy/*.mpy build/mpy/layouts/*.mpy | wc -l | tr -d ' '` modules" \
	  "(`cat davega/gui/*.py davega/gui/layouts/*.py | wc -c | tr -d ' '` B source" \
	  "-> `cat build/mpy/*.mpy build/mpy/layouts/*.mpy | wc -c | tr -d ' '` B bytecode)"

davega-install: mpy
	@python3 davega/tools/webrepl-run.py --host $(DAVEGA_HOST) --mkdir /gui \
	  --mkdir /gui/layouts \
	  $(foreach m,$(MODULES),--put build/mpy/$(m).mpy:/gui/$(m).mpy) \
	  $(foreach l,$(LAYOUTS),--put build/mpy/layouts/$(l).mpy:/gui/layouts/$(l).mpy) \
	  --put build/mpy/runner.mpy:/gui/runner.mpy \
	  --put build/mpy/boot.mpy:/gui/boot.mpy \
	  --put davega/start.py:/start.py
	@echo "installed - restart the display when you want it"

# Source instead of bytecode, for when you want to read a traceback with real
# line numbers on the device.
davega-install-src:
	@python3 davega/tools/webrepl-run.py --host $(DAVEGA_HOST) --mkdir /gui \
	  --mkdir /gui/layouts \
	  $(foreach m,$(MODULES),--put davega/gui/$(m).py:/gui/$(m).py) \
	  $(foreach l,$(LAYOUTS),--put davega/gui/layouts/$(l).py:/gui/layouts/$(l).py) \
	  --put davega/gui/runner.py:/gui/runner.py \
	  --put davega/gui/boot.py:/gui/boot.py \
	  --put davega/start.py:/start.py
	@echo "installed as source - restart the display when you want it"

# End to end, in the MicroPython the display actually runs. Same argument as
# test-lisp: the interpreter is part of what is under test.
test-device:
	@./davega/tests/device/run.sh

# Regenerate the screen mockups from the code that draws them.
mockups:
	@python3 davega/tools/mockup.py
	@echo "open davega/mockups/index.html"

webrepl: $(WEBREPL)
	@echo "1. hold UP+DOWN and power-cycle the board - the DAVEGA has no switch,"
	@echo "   it boots when the ESC powers it"
	@echo "2. the display should say: starting in WebREPL mode / WiFi AP: davega-x-..."
	@echo "3. join that davega-x-... network (this machine loses the board bridge)"
	@echo "4. connect to ws://192.168.4.1:8266 in the page that just opened"
	@echo ""
	@echo "then paste davega/tools/recon.py and call recon()"
ifeq ($(UNAME),Darwin)
	@open $(WEBREPL)
else
	@xdg-open $(WEBREPL) >/dev/null 2>&1 || echo "open $(WEBREPL)"
endif

dual-check: check
	$(call run_qml,dual-check)

set-app: check
	$(call run_qml,set-app)

faults: check
	$(call run_qml,faults)

ppm-watch: check
	$(call run_qml,ppm-watch)

ppm-cal: check
	$(call run_qml,ppm-calibrate)

apply-appconf-local: check
	$(call run_qml,apply-appconf-local)

apply-appconf: check
	@echo "writing local appconf (app_to_use)"
	$(call run_qml,apply-appconf)

upload-lisp: check
	@echo "uploading $(LISP)"
	$(call run_qml,lisp-upload)

upload-hello: check
	@$(MAKE) --no-print-directory upload-lisp LISP=lisp/src/hello.lisp

lisp-stats: check
	$(call run_qml,lisp-probe)

lisp-stop: check
	$(call run_qml,lisp-halt)

clean:
	@rm -rf $(BUILD)
