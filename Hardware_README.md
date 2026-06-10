# CPTR480 Quadrature SDR Hardware Documentation

This repository contains the KiCad schematics, PCB layouts, and Bills of Materials for the CPTR480 Quadrature Software Defined Radio (SDR) receiver board designed by McCormick and Mendoza.

## System Architecture

The radio is a direct-conversion, quadrature-sampling receiver (commonly utilizing a Tayloe Detector topology) managed by a Raspberry Pi Pico. The RF front-end downconverts the incoming antenna signal directly to baseband I (In-phase) and Q (Quadrature) audio signals, which are digitized and processed by the RP2040 microcontroller. 

### Core Hardware Modules

1. **Microcontroller & Digital Core**
   - **Raspberry Pi Pico (RP2040)**: The brains of the SDR. Handles I2C UI/Hardware control, I2S digital audio streams, DSP, and SD card interfacing.

2. **RF Front-End & Mixing (Tayloe Detector)**
   - **SN74CBT3253CDBR**: Dual 1-of-4 FET Multiplexer/Demultiplexer. This high-speed analog switch acts as the quadrature mixer, sequentially sampling the incoming RF signal at the Local Oscillator frequency to produce differential baseband I and Q signals.
   - **SN74AC74DR**: Dual D-Type Positive-Edge-Triggered Flip-Flop, typically used to accurately divide the synthesized clock to drive the Tayloe detector switches with precise 90-degree phase offsets.

3. **Clock Generation**
   - **Si5351A-B-GT**: I2C-programmable ANY-frequency CMOS clock generator. Driven by a high-precision **24.576 MHz TCXO** (ASTX-H11) for ultra-low drift, it synthesizes the Local Oscillator (LO) frequencies. For quadrature mixing, it is configured to output signals at 4x the target listen frequency.

4. **Baseband Amplification**
   - **INA821ID**: High-precision instrumentation amplifiers used to convert the differential outputs of the Tayloe mixer to single-ended signals and apply initial low-noise gain.
   - **OPA1612AxD**: Dual SoundPlus™ high-performance bipolar-input audio operational amplifiers for active low-pass filtering and final baseband gain stages.

5. **Data Converters (Audio/Baseband)**
   - **PCM1808PWR**: 24-bit, 96-kHz Stereo ADC. Digitizes the analog I and Q baseband signals and sends them to the Pico over I2S.
   - **PCM5102A**: 32-bit, 384-kHz Stereo DAC with integrated PLL. Converts the final DSP-processed audio or playback audio from the Pico back to analog for the headphone output.

6. **User Interface**
   - **0.96" OLED Display**: 128x64 pixels, I2C interface.
   - **Rotary Encoder (Alps EC11)**: Includes a push-button switch for frequency tuning and menu navigation.
   - **Tactile Button**: For additional UI control inputs.

7. **Power Management**
   - **TPS7A2045PDQN**: 4.5V Ultra-Low-Noise LDO regulator for sensitive analog components.
   - **TPS72733DSER**: 3.3V Low-Dropout regulator for clean digital/mixed-signal voltage rails.

8. **Connectivity**
   - **BNC Connector (Amphenol)**: Main RF antenna input.
   - **3.5mm Audio Jacks (CUI SJ-3523-SMT)**: For SDR audio output and DAC direct output.
   - **MicroSD Card Slot**: Connected via SPI for playing WAV files or potentially recording IQ streams.

## KiCad Project Structure

The hardware source files are located in the `Radio_Receiver_McCormick_Mendoza` directory. The schematic is built hierarchically:

- **`Radio_Receiver_McCormick_Mendoza.kicad_sch`**: The top-level schematic tying all functional blocks together.
- **`antenna.kicad_sch` / `low_pass_filter.kicad_sch`**: Front-end filtering blocks.
- **`mixer.kicad_sch`**: The Tayloe detector and RF switching core.
- **`clock_generator.kicad_sch`**: Si5351 synthesizer and TCXO.
- **`ADC-24bit.kicad_sch` / `Audio_DAC.kicad_sch`**: Data converter sub-sheets.
- **`raspberry_pi_pico.kicad_sch`**: MCU pinning and decoupling.
- **`power_supply.kicad_sch`**: LDOs and power distribution network.
- **`Display.kicad_sch` / `Angle_Encoder.kicad_sch`**: UI peripherals.

## Bill of Materials (BOM)

The complete component list, including LCSC part numbers for JLCPCB assembly, can be found in `Radio_Receiver_McCormick_Mendoza.csv`.
