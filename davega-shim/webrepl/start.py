# UNTESTED. A candidate fix for the DAVEGA X version gate that needs no shim,
# no firmware build and no flashing - just this file on the device.
#
# Upload as /start.py over WebREPL (hold UP+DOWN while booting). The firmware
# has executed a user start.py at boot since v5.03.
#
# WHY THIS MIGHT WORK
#   The v5.06 image places two functions in frozen/run_standard.py:
#       is_compatible_vesc_version
#       assert_compatible_vesc_version
#   They are module-level functions, and MicroPython resolves a module-level
#   call through the module's globals at call time. Rebinding the attribute
#   before the app calls it should therefore take effect.
#
#   The ordering is right: frozen/main.py runs its boot steps as
#       ... maybe_webrepl  exec_custom_start  boot_fw
#   so this file executes before the application starts.
#
# WHY IT MIGHT NOT
#   - The caller may hold its own reference (from ... import ...), in which
#     case patching the module changes nothing.
#   - The names may differ on your firmware version.
#   Either makes this a no-op, not a brick. Verify with recon.py first:
#       probe('frozen.run_standard')
#
# GETTING OUT
#   maybe_webrepl runs BEFORE exec_custom_start, so holding UP+DOWN at boot
#   reaches a REPL no matter what this file does. You can always delete it.
#
# The proxy shim in this repo is the tested path. This is the cheaper one, if
# it works - and if it does, please say so.

_PATCHED = False

try:
    import frozen.run_standard as _rs

    _real_is_compat = getattr(_rs, "is_compatible_vesc_version", None)
    _real_assert = getattr(_rs, "assert_compatible_vesc_version", None)

    if _real_is_compat is not None:
        _rs.is_compatible_vesc_version = lambda *a, **k: True
        _PATCHED = True
    if _real_assert is not None:
        _rs.assert_compatible_vesc_version = lambda *a, **k: None
        _PATCHED = True

    print("start.py: version gate patched" if _PATCHED
          else "start.py: gate functions not found - firmware differs, doing nothing")
except Exception as e:                      # noqa: BLE001
    # Never take the boot down with us. A display that boots unpatched is a
    # far better outcome than one that does not boot.
    print("start.py: patch failed, continuing unpatched: %s" % e)
