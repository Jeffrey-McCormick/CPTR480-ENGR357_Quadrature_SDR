from machine import I2S, Pin, PWM
import time
import struct
import math

# ==========================================
# 1. USER'S DAC CLASS (PCM5102A)
# ==========================================
class DAC:
    def __init__(self, bck_pin=15, ws_pin=16, data_pin=14, mute_pin=6, i2s_id=0, sample_rate=44100, bits=16, buffer_size=20480):
        self.bck_pin = bck_pin
        self.ws_pin = ws_pin
        self.data_pin = data_pin
        self.i2s_id = i2s_id
        self.sample_rate = sample_rate
        self.bits = bits
        self.buffer_size = buffer_size
        self.i2s = None

        self.sck_fallback = PWM(Pin(17))
        self.sck_fallback.freq(11289600)
        self.sck_fallback.duty_u16(32768)

        self.mute_control = None
        if mute_pin is not None:
            self.mute_control = Pin(mute_pin, Pin.OUT)
            self.unmute()

        self.set_stereo()

    def mute(self):
        if self.mute_control:
            self.mute_control.value(0)
            
    def unmute(self):
        if self.mute_control:
            self.mute_control.value(1)

    def _configure_i2s(self, format_mode):
        if self.i2s:
            self.i2s.deinit() 
        
        self.i2s = I2S(
            self.i2s_id,
            sck=Pin(self.bck_pin),
            ws=Pin(self.ws_pin),
            sd=Pin(self.data_pin),
            mode=I2S.TX,
            bits=self.bits,
            format=format_mode,
            rate=self.sample_rate,
            ibuf=self.buffer_size
        )

    def set_mono(self):
        self._configure_i2s(I2S.MONO)
        print(f"PCM5102A configured for Dual-Mono at {self.sample_rate}Hz")

    def set_stereo(self):
        self._configure_i2s(I2S.STEREO)
        print(f"PCM5102A configured for Stereo at {self.sample_rate}Hz")

    def write_buffer(self, audio_buffer):
        if self.i2s:
            return self.i2s.write(audio_buffer)
        return 0
        
    def close(self):
        self.mute()
        time.sleep_ms(20)
        if self.i2s:
            self.i2s.deinit()

# ==========================================
# 2. INTEGRATION & ADC SETUP (PCM1808)
# ==========================================

# --- Pin Definitions ---
LED_PIN = 5

# ADC (RX) Pins - Assigned to I2S ID 0
ADC_BCK_PIN = 10
ADC_WS_PIN = 11
ADC_DATA_PIN = 12

# Threshold to trigger the LED based on ADC input
AUDIO_THRESHOLD = 50000 

if __name__ == "__main__":
    print("Starting System...")
    
    # Initialize LED
    led = Pin(LED_PIN, Pin.OUT)
    led.value(0)

    # Initialize DAC on I2S ID 1 (Avoids conflict with ADC on ID 0)
    print("Initializing DAC (PCM5102A)...")
    dac = DAC(i2s_id=1) 
    dac.unmute() 

    # Initialize ADC on I2S ID 0
    print("Initializing ADC (PCM1808)...")
    adc = I2S(
        0,
        sck=Pin(ADC_BCK_PIN),
        ws=Pin(ADC_WS_PIN),
        sd=Pin(ADC_DATA_PIN),
        mode=I2S.RX,
        bits=32,          # PCM1808 24-bit data padded to 32-bit by MicroPython
        format=I2S.STEREO,
        rate=44100,
        ibuf=20480
    )

    # ==========================================
    # 3. BUFFER GENERATION (MEMORY OPTIMIZED)
    # ==========================================
    print("Generating Audio Buffer...")
    sample_rate = 44100
    # Use 441Hz. This exactly divides into 44100 (100 samples per cycle).
    # This allows us to make a perfectly looping buffer without audio clicking.
    freq = 441  
    num_samples = 1000  # 10 full cycles
    
    # TX Buffer for DAC (16-bit Stereo = 4 bytes per sample)
    tx_buf = bytearray(num_samples * 4) 

    # Populate the TX buffer with the Sine wave
    for i in range(num_samples):
        val = int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        struct.pack_into("<hh", tx_buf, i * 4, val, val) # L and R channels
    
    # RX Buffer for ADC (32-bit Stereo = 8 bytes per sample)
    # We read back the same number of samples we write
    rx_buf = bytearray(num_samples * 8) 

    # ==========================================
    # 4. FULL DUPLEX LOOP
    # ==========================================
    print("Beginning Loopback Test. Connect DAC Output to ADC Input.")
    try:
        while True:
            # 1. Output the audio chunk to the DAC
            dac.write_buffer(tx_buf)
            
            # 2. Immediately read incoming audio from the ADC
            num_bytes_read = adc.readinto(rx_buf)
            print(num_bytes_read)
            
            # 3. Process the incoming audio to control the LED
            if num_bytes_read > 0:
                num_rx_samples = num_bytes_read // 4
                samples = struct.unpack('<' + 'i' * num_rx_samples, rx_buf[:num_bytes_read])
                
                max_amplitude = 0
                
                # Check every 4th sample to save CPU cycles and maintain audio stream speed
                for i in range(0, len(samples), 4):
                    amplitude = abs(samples[i] >> 8) 
                    if amplitude > max_amplitude:
                        max_amplitude = amplitude
                
                # Trigger the LED
                if max_amplitude > AUDIO_THRESHOLD:
                    led.value(1)
                else:
                    led.value(0)
                    
    except KeyboardInterrupt:
        print("\nStopping...")
        dac.close()
        adc.deinit()
        led.value(0)
        print("Hardware safely shut down.")