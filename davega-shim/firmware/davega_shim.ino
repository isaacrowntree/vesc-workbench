/*
 * DAVEGA <-> VESC FW7 translation shim.
 *
 * Sits inline on the UART between a VESC running FW 7.x and a DAVEGA X.
 * The VESC UART protocol is byte-identical between FW 6.00 and 7.x; the DAVEGA
 * only refuses to talk because of two bytes in the COMM_FW_VERSION reply.
 * So: pass everything through, and rewrite those two bytes (+ CRC) on the way
 * to the display.
 *
 * DAVEGA -> VESC : verbatim passthrough.
 * VESC -> DAVEGA : COMM_FW_VERSION responses rewritten to report 6.00.
 *
 * Verified against the Python reference in ../shim.py (see ../test_shim.py).
 *
 * Wiring (all 3.3V logic, common ground):
 *   VESC TX   -> UART_VESC RX        UART_VESC TX -> VESC RX
 *   DAVEGA TX -> UART_DISP RX        UART_DISP TX -> DAVEGA RX
 *   VESC 5V/GND -> board VIN/GND
 */

#include <Arduino.h>

// ---- board wiring -----------------------------------------------------------
#if defined(ARDUINO_ARCH_ESP32)
  #define UART_VESC Serial1
  #define UART_DISP Serial2
  static const int VESC_RX = 16, VESC_TX = 17;
  static const int DISP_RX = 18, DISP_TX = 19;
#elif defined(ARDUINO_ARCH_RP2040)
  #define UART_VESC Serial1
  #define UART_DISP Serial2
#else
  #define UART_VESC Serial1
  #define UART_DISP Serial2
#endif

static const uint32_t BAUD = 115200;

// ---- VESC protocol ----------------------------------------------------------
static const uint8_t COMM_FW_VERSION = 0;
static const uint8_t STOP_BYTE       = 3;
static const uint8_t SPOOF_MAJOR     = 6;
static const uint8_t SPOOF_MINOR     = 0;

// bldc/util/crc.c - CCITT poly 0x1021, init 0
static uint16_t crc16(const uint8_t *buf, uint16_t len) {
  uint16_t cksum = 0;
  for (uint16_t i = 0; i < len; i++) {
    uint16_t idx = ((cksum >> 8) ^ buf[i]) & 0xFF;
    uint16_t v = idx << 8;
    for (uint8_t b = 0; b < 8; b++) v = (v & 0x8000) ? ((v << 1) ^ 0x1021) : (v << 1);
    cksum = v ^ (cksum << 8);
  }
  return cksum;
}

// ---- streaming frame assembler ---------------------------------------------
static const uint16_t BUF_MAX     = 1024;
static const uint32_t IDLE_FLUSH_US = 4000;   // don't hold a partial frame forever

static uint8_t  buf[BUF_MAX];
static uint16_t buf_len = 0;
static uint32_t last_rx_us = 0;
uint32_t rewrites = 0;

static void emit(const uint8_t *p, uint16_t n) { UART_DISP.write(p, n); }

// Header size for a start byte, or 0 if it isn't one.
static uint8_t hdr_for(uint8_t s) { return (s == 2) ? 2 : (s == 3) ? 3 : (s == 4) ? 4 : 0; }

// Try to consume one complete, CRC-valid frame from the front of buf.
// Returns bytes consumed, or 0.
static uint16_t try_frame() {
  if (buf_len == 0) return 0;
  uint8_t hdr = hdr_for(buf[0]);
  if (hdr == 0 || buf_len < hdr) return 0;

  uint32_t n = (hdr == 2) ? buf[1]
             : (hdr == 3) ? ((uint32_t)buf[1] << 8 | buf[2])
                          : ((uint32_t)buf[1] << 16 | (uint32_t)buf[2] << 8 | buf[3]);
  uint32_t total = hdr + n + 3;
  if (n == 0 || total > BUF_MAX) return 0;      // bogus length
  if (buf_len < total) return 0;                // wait for more

  uint8_t *payload = buf + hdr;
  uint16_t crc_rx = ((uint16_t)buf[hdr + n] << 8) | buf[hdr + n + 1];
  if (buf[total - 1] != STOP_BYTE || crc_rx != crc16(payload, n)) return 0;

  if (n >= 3 && payload[0] == COMM_FW_VERSION &&
      (payload[1] != SPOOF_MAJOR || payload[2] != SPOOF_MINOR)) {
    payload[1] = SPOOF_MAJOR;
    payload[2] = SPOOF_MINOR;
    uint16_t c = crc16(payload, n);
    buf[hdr + n]     = c >> 8;
    buf[hdr + n + 1] = c & 0xFF;
    rewrites++;
  }
  emit(buf, total);
  return total;
}

static void drop_front(uint16_t k) {
  memmove(buf, buf + k, buf_len - k);
  buf_len -= k;
}

// True if the front of buf could still grow into a valid frame.
static bool may_complete() {
  uint8_t hdr = hdr_for(buf[0]);
  if (hdr == 0) return false;
  if (buf_len < hdr) return true;
  uint32_t n = (hdr == 2) ? buf[1]
             : (hdr == 3) ? ((uint32_t)buf[1] << 8 | buf[2])
                          : ((uint32_t)buf[1] << 16 | (uint32_t)buf[2] << 8 | buf[3]);
  return (hdr + n + 3) <= BUF_MAX && buf_len < (hdr + n + 3);
}

static void pump() {
  for (;;) {
    if (buf_len == 0) return;
    uint16_t used = try_frame();
    if (used) { drop_front(used); continue; }
    if (may_complete()) return;             // hold, wait for more bytes
    emit(buf, 1);                           // junk / not a frame: pass it on
    drop_front(1);
  }
}

void setup() {
#if defined(ARDUINO_ARCH_ESP32)
  UART_VESC.begin(BAUD, SERIAL_8N1, VESC_RX, VESC_TX);
  UART_DISP.begin(BAUD, SERIAL_8N1, DISP_RX, DISP_TX);
#else
  UART_VESC.begin(BAUD);
  UART_DISP.begin(BAUD);
#endif
}

void loop() {
  // DAVEGA -> VESC: straight through, never touched.
  while (UART_DISP.available()) UART_VESC.write(UART_DISP.read());

  // VESC -> DAVEGA: through the translator.
  bool got = false;
  while (UART_VESC.available() && buf_len < BUF_MAX) {
    buf[buf_len++] = UART_VESC.read();
    got = true;
  }
  if (got) { last_rx_us = micros(); pump(); }

  // Never hold a partial frame indefinitely - if the line goes quiet, release it.
  if (buf_len && (micros() - last_rx_us) > IDLE_FLUSH_US) {
    emit(buf, 1);
    drop_front(1);
    pump();
    last_rx_us = micros();
  }

  // Overflow guard: should never happen, but don't wedge if it does.
  if (buf_len >= BUF_MAX) { emit(buf, buf_len); buf_len = 0; }
}
