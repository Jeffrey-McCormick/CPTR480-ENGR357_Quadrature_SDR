# Overview

MicroPython firmware for the CPTR480 Quadrature SDR board (RP2040 / Pico-class). The software drives the Si5351 clock generator for quadrature LO signals, an SSD1306 OLED and rotary encoder for the user interface, an analog filter MUX, and (separately) SD-card WAV playback through a PCM5102A DAC over I2S.

**Entry point:** `main.py` configures the Si5351, then launches the `SDRApp` menu.

**Typical pin map (shared across modules):**

| Signal | GPIO |
|--------|------|
| I2C SDA | 12 |
| I2C SCL | 13 |
| Encoder A / B | 20 / 21 |
| Encoder button | 22 |
| DAC I2S BCK / WS / DATA | 15 / 16 / 14 |
| DAC mute (XSMT) | 6 |
| SD SPI CS / SCK / MOSI / MISO | 1 / 2 / 3 / 0 |
| Filter MUX CTL1 / CTL2 | 19 / 18 |

Library copies of `si5351.py` and `ssd1306.py` live in `Bringup/Load_files/` and are imported from there during bringup; production code expects them on the device root alongside the app modules.

---

## Drivers

### Bringup

Standalone scripts used during hardware validation. Each can be uploaded and run independently on the board.

| Component | File | Function | Pass/Fail |
|-----------|------|----------|-----------|
| LED | `Bringup/led_blink.py` | Blinks GPIO5 to confirm basic GPIO and upload toolchain | — |
| I2C bus | `Bringup/i2c_scan.py` | Scans I2C0 (SDA=12, SCL=13); expects Si5351 at `0x60`, OLED at `0x3C` | — |
| OLED display | `Bringup/oled_test.py` | Full exercise suite for the SSD1306 (text, lines, animation, contrast, power cycle) via `ssd1306.py` | — |
| Rotary encoder + button | `Bringup/rotary_encoder.py` | `QuadratureEncoder` (detent counting on GPIO 20/21) and `ButtonHandler` (debounced click + long-press on GPIO 22) | — |
| Si5351 clock | `Bringup/si5351_test.py` | Register R/W test, PLL lock check, 10.24 MHz quadrature setup, frequency sweep with integer-divider validation | — |
| Filter MUX | `Bringup/filter_mux_control.py` | Drives CTL1 (GPIO19) and CTL2 (GPIO18) to select one of four analog filter paths | — |
| Si5351 driver | `Bringup/Load_files/si5351.py` | I2C driver: PLL/multiplier config, per-clock dividers, phase offset, output enable | — |
| OLED driver | `Bringup/Load_files/ssd1306.py` | Standard MicroPython SSD1306 I2C framebuffer driver | — |

**`si5351_test.py` details:** Configures PLLA with N=25 (VCO = 24.576 MHz × 25 = 614.4 MHz), sets CLK0/1/2 dividers, and applies phase offsets of 0°, 90°, and 180° via `set_phase()`. The `is_integer_divider()` helper ensures only frequencies that divide the VCO evenly are programmed during the sweep.

**`rotary_encoder.py` details:** Encoder uses IRQ-driven quadrature decoding with detent aggregation (`ppr` parameter). `ButtonHandler` distinguishes short click (on release before 600 ms) from long press (held ≥ 600 ms); the main app uses long press for "back" navigation.

---

### UI

The menu system is split between a legacy `Menu` renderer and a page-stack navigation layer.

| File | Role |
|------|------|
| `menu.py` | **`Menu`** — draws a scrollable option list on the 128×64 OLED. **`SDRApp`** — wires I2C/OLED, encoder, and button; owns the frequency list and `NavStack`; main event loop running cooperatively via `asyncio`. |
| `ui/page.py` | **`Page`** base class (`on_enter`, `on_exit`, `handle_input`, `draw`). **`NavStack`** — push/pop/replace for nested screens; root page cannot be popped. |
| `ui/menu_page.py` | **`MenuPage`** — builds a `Menu` from `MenuItem` definitions; click navigates to a child page or runs an action; optional back row. |
| `ui/freq_pages.py` | **`ValueEditorPage`** — encoder adjusts a numeric value in Hz; click saves. **`AddFreqPage`** — adds a frequency to the sorted `app.freqs` list. **`FreqListPage`** — lists saved frequencies for remove or listen actions. |
| `ui/music_pages.py` | **`MusicListPage`** — selectable list of WAV files from the SD card. **`PlaybackPage`** — playback controls (Play, Pause, Exit) for a track, interfacing with `PlaybackController`. |
| `ui/screen_mode_page.py` | **`ScreenModePage`** — placeholder page for displaying SD card photos (Coming Soon). |

**Navigation model:**

- Rotate encoder → move selection up/down.
- Short click → confirm / enter submenu.
- Long press → go back (when not on root menu).

**Main menu options (FrohnePod):**

1. **Radio** — enter submenu to Add, Remove, or Listen to SDR frequencies.
2. **Music Player** — browse `.wav` files on the SD card and enter the playback screen.
3. **Screen Mode** — enter submenu for screen viewing modes.

`main.py` calls `configure_si5351()` before starting the app, setting CLK0 to 1.42 MHz as the initial LO.

---

### Audio Stream

WAV playback from the SD card is handled cooperatively with `asyncio` (not a second RP2040 core). The design keeps the I2S feed non-blocking relative to other tasks by yielding whenever the hardware ring buffer is full.

| File | Role |
|------|------|
| `sd.py` | SPI mount helper (`mount_sd`) and `list_wav_files` for `.wav` files on `/sd`. |
| `sdcard.py` | Low-level SPI SD-card driver (`readblocks` / `writeblocks` for `os.mount`). Busy-poll read path tuned for streaming throughput. |
| `player/PlaybackController.py` | Async WAV streamer: mounts SD, opens PCM5102A via `DAC`, spawns `_stream_task` on `play()`. |

**`PlaybackController` flow:**

1. `initialize()` — mount SD, create `DAC` in non-blocking stereo mode (muted).
2. `play(filename)` — skip WAV header to PCM `data` chunk, start asyncio task.
3. `_stream_task` — reads chunks from the file, writes to I2S directly via non-blocking `write()`, and yields to the UI event loop via `asyncio.sleep_ms(10)` when the hardware ring buffer is full. Unmutes after two buffered chunks; on EOF waits 300 ms for the ring to drain before muting.
4. `pause()` / `resume()` / `stop()` — mute control and task cancellation with a generation counter so stale tasks cannot clobber state.

**Expected audio format:** 16-bit stereo PCM WAV at the DAC sample rate (default 44.1 kHz). Mono or other formats are not handled.

**Standalone usage:** `sd.py` can be run directly (`python sd.py` on-device) to play the first track found on the card.

![Watch this lol](./_Media/IMG_4193.MOV)

---

### DAC

`dac.py` wraps the RP2040 I2S peripheral for a PCM5102A DAC.

| Feature | Detail |
|---------|--------|
| Pins | BCK=15, WS=16, DATA=14, XSMT mute=6, MCLK=17 |
| Modes | Stereo (default) or mono via `set_stereo()` / `set_mono()` |
| Blocking vs non-blocking | `nonblocking=True` enables non-blocking writes and lets the `PlaybackController` cooperatively yield while the buffer is full |
| Mute | `mute()` / `unmute()` drive XSMT LOW/HIGH |
| Shutdown | `close()` — clears IRQ, mutes, deinits I2S |

The DAC requires an external Master Clock (`MCLK`). `dac.py` sets up a PWM signal on Pin 17 at `256 * sample_rate` to satisfy the PCM5102A's MCLK requirement.

The `__main__` block generates a 440 Hz sine wave for a quick hardware smoke test.

---

## Outcome

### Problems

- **Listen Freq is a stub** — selecting a frequency in `FreqListPage` only prints to the serial console; it does not yet call `Si5351` to retune the LO or select a filter MUX channel.
- **Si5351 config split** — clock setup lives in `main.py` (`configure_si5351`) while the UI frequency list is separate; there is no shared tuning API yet.
- **Module path** — `menu.py` falls back to `Bringup/` on import error; deployed firmware should copy `si5351.py`, `ssd1306.py`, and `rotary_encoder.py` to the device root to avoid path hacks.
- **Encoder debug prints** — `QuadratureEncoder.on_change` still prints on every edge; noisy during normal UI use.
- **WAV assumptions** — playback expects 16-bit stereo PCM; no sample-rate negotiation or resampling.
- **Filter MUX unused in app** — `filter_mux_control.py` is bringup-only; channel selection is not tied to frequency or listen mode.
