"""
DAC code
"""
from machine import I2S, Pin, PWM
import time

class DAC:
    def __init__(self, bck_pin=15, ws_pin=16, data_pin=14, mute_pin=6, i2s_id=0, sample_rate=22050, bits=16, buffer_size=2000):
        """
        Initializes the I2S interface for the PCM5102A.
        """
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

        # Set up the optional hardware mute pin (XSMT on PCM5102A)
        self.mute_control = None
        if mute_pin is not None:
            self.mute_control = Pin(mute_pin, Pin.OUT)
            self.unmute() # Start muted to prevent pops during init

        # Default to Stereo initialization
        self.set_stereo()


    def mute(self):
        """Pulls the XSMT pin LOW to soft-mute the DAC output."""
        if self.mute_control:
            self.mute_control.value(0)
            
    def unmute(self):
        """Pulls the XSMT pin HIGH to unmute the DAC output."""
        if self.mute_control:
            self.mute_control.value(1)

    def _configure_i2s(self, format_mode):
        """Internal helper to set up or re-initialize the I2S hardware."""
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
        """Configures the I2S stream for Mono (Pico duplicates L/R internally)."""
        self._configure_i2s(I2S.MONO)
        print(f"PCM5102A configured for Dual-Mono at {self.sample_rate}Hz")

    def set_stereo(self):
        """Configures the I2S stream for true Stereo output."""
        self._configure_i2s(I2S.STEREO)
        print(f"PCM5102A configured for Stereo at {self.sample_rate}Hz")

    def write_buffer(self, audio_buffer):
        """Writes audio data. Call unmute() before streaming if currently muted."""
        if self.i2s:
            return self.i2s.write(audio_buffer)
        return 0
        
    def close(self):
        """Mutes the DAC and safely shuts down the I2S peripheral."""
        self.mute()
        time.sleep_ms(20) # Give the PCM5102A a moment to ramp down gracefully
        if self.i2s:
            self.i2s.deinit()

if __name__ == "__main__":
    import struct, math
    dac = DAC()
    dac.unmute()  # explicit, just in case

    # Generate a 440Hz sine tone, 1 second worth
    sample_rate = 44100
    freq = 440
    num_samples = sample_rate  # 1 second
    buf = bytearray(num_samples * 4)  # stereo, 16-bit = 4 bytes/frame

    for i in range(num_samples):
        val = int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        struct.pack_into("<hh", buf, i * 4, val, val)  # L and R
    
    dac.write_buffer(buf)