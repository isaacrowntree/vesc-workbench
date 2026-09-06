# LaCroix Unity / DAVEGA workbench.
#
# Everything talks to the board over the phone's TCP bridge:
#   phone VESC Tool -> BLE -> Unity, Start page -> "Wireless Bridge to Computer (TCP)"
# Desktop VESC Tool must be CLOSED - the bridge accepts one client.
#
#   make help

# Load a board profile if one is given: make davega-debug PROFILE=profiles/nazare-unity.mk
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
LISP    ?= davega-shim/lisp/davega_shim.lisp
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
	@echo "  make ppm-watch     - continuous PPM readout, prints only on change"
	@echo "  make ppm-cal       - live Hoyt Puck calibration (follow the prompts)"
	@echo "  make upload-hello  - upload+run the minimal LispBM smoke test"
	@echo "  make upload-lisp   - upload+run LISP=$(LISP)"
	@echo "  make davega-debug  - DAVEGA proxy health check with a verdict"
	@echo "  make lisp-stats    - LispBM heap/cpu stats"
	@echo "  make lisp-stop     - stop the running LispBM script"
	@echo ""
	@echo "DAVEGA X display (its own WiFi AP, not the board):"
	@echo "  make webrepl       - fetch the WebREPL client and open it locally"
	@echo ""
	@echo "Offline:"
	@echo "  make test          - all host-side tests"
	@echo "  make test-py       - shim reference + payload layout tests"
	@echo "  make test-lisp     - run the LispBM logic in the upstream REPL (Docker)"
	@echo ""
	@echo "Vars: HOST=$(HOST) PORT=$(PORT) CANID=$(CANID) SECS=$(SECS)"
	@echo "      PROFILE=$(PROFILE)   (e.g. profiles/nazare-unity.mk)"

# ---- offline tests ---------------------------------------------------------
test: test-py test-lisp

test-py:
	@cd davega-shim && python3 test_shim.py && python3 test_layout.py

test-lisp:
	@./tests/run-lisp-tests.sh

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
	     tools/$(1).qml > $(BUILD)/$(1).qml
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
.SECONDARY: build/davega_proxy_live.lisp build/davega_proxy_safe.lisp

# The proxy variants differ only in their output policy, so they are assembled
# from the shared core rather than kept as two near-identical copies.
build/davega_proxy_%.lisp: davega-shim/lisp/proxy.lisp davega-shim/lisp/reader.lisp davega-shim/lisp/proxy-main.lisp davega-shim/lisp/output-%.lisp
	@mkdir -p $(BUILD)
	@cat $^ > $@

build/proxy_%.min.lisp: build/davega_proxy_%.lisp tools/minify-lisp.py
	@mkdir -p $(BUILD)
	@python3 tools/minify-lisp.py $< $@ $(CANID)

build/davega_shim.min.lisp: davega-shim/lisp/davega_shim.lisp tools/minify-lisp.py
	@mkdir -p $(BUILD)
	@python3 tools/minify-lisp.py $< $@ $(CANID)

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

webrepl: $(WEBREPL)
	@echo "1. hold UP+DOWN while the DAVEGA boots - it raises its own WiFi AP"
	@echo "2. join that AP (this machine loses the board bridge until you leave)"
	@echo "3. connect to ws://192.168.4.1:8266 in the page that just opened"
	@echo ""
	@echo "then paste davega-shim/webrepl/recon.py and call recon()"
ifeq ($(UNAME),Darwin)
	@open $(WEBREPL)
else
	@xdg-open $(WEBREPL) >/dev/null 2>&1 || echo "open $(WEBREPL)"
endif

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
	@$(MAKE) --no-print-directory upload-lisp LISP=tools/hello.lisp

lisp-stats: check
	$(call run_qml,lisp-probe)

lisp-stop: check
	$(call run_qml,lisp-halt)

clean:
	@rm -rf $(BUILD)
