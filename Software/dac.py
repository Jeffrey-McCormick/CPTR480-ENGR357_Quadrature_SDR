"""
DAC code
"""
from machine import I2S, Pin
import time


class DAC:
    def __init__(
        self,
        bck_pin=15,
        ws_pin=16,
        data_pin=14,
        mute_pin=6,
        mclk_pin=17,
        i2s_id=0,
        sample_rate=44100,
        bits=16,
        buffer_size=40000,
        nonblocking=True,
    ):
        """
        Initializes the I2S interface for the PCM5102A.
        """
        self.bck_pin = bck_pin
        self.ws_pin = ws_pin
        self.data_pin = data_pin
        self.mclk_pin = mclk_pin
        self.i2s_id = i2s_id
        self.sample_rate = sample_rate
        self.bits = bits
        self.buffer_size = buffer_size
        self.nonblocking = nonblocking
        self.i2s = None
        self._drain_handler = None

        self.mclk = None
        if self.mclk_pin is not None:
            from machine import PWM
            self.mclk = PWM(Pin(self.mclk_pin))
            self.mclk.freq(self.sample_rate * 256)
            self.mclk.duty_u16(32768)

        self.mute_control = None
        if mute_pin is not None:
            self.mute_control = Pin(mute_pin, Pin.OUT)
            self.mute()

        self.set_stereo()

    def set_drain_handler(self, handler):
        """handler() is called when the I2S ring has space for more audio."""
        self._drain_handler = handler

    def _on_i2s_irq(self, i2s):
        if self._drain_handler:
            self._drain_handler()

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
            ibuf=self.buffer_size,
        )

        if self.nonblocking:
            self.i2s.irq(self._on_i2s_irq)
        else:
            self.i2s.irq(None)

    def set_mono(self):
        """Configures the I2S stream for Mono (Pico duplicates L/R internally)."""
        self._configure_i2s(I2S.MONO)
        print(f"PCM5102A configured for Dual-Mono at {self.sample_rate}Hz")

    def set_stereo(self):
        """Configures the I2S stream for true Stereo output."""
        self._configure_i2s(I2S.STEREO)
        mode = "non-blocking" if self.nonblocking else "blocking"
        print(f"PCM5102A configured for Stereo at {self.sample_rate}Hz ({mode})")

    def write(self, audio_buffer, length=None):
        """
        Write audio to I2S.
        Non-blocking: returns bytes accepted immediately (may be partial).
        Blocking: loops until the full chunk is queued.
        """
        if not self.i2s:
            return 0

        view = memoryview(audio_buffer)
        if length is not None:
            view = view[:length]

        if self.nonblocking:
            return self.i2s.write(view)

        offset = 0
        total = len(view)
        while offset < total:
            offset += self.i2s.write(view[offset:])
        return offset

    def write_buffer(self, audio_buffer, length=None):
        """Alias for write(); kept for older callers."""
        return self.write(audio_buffer, length)

    def close(self):
        """Mutes the DAC and safely shuts down the I2S peripheral."""
        self._drain_handler = None
        if self.i2s:
            self.i2s.irq(None)
        self.mute()
        time.sleep_ms(20)
        if self.i2s:
            self.i2s.deinit()


if __name__ == "__main__":
    import struct
    import math

    dac = DAC(nonblocking=False)
    dac.unmute()

    sample_rate = 44100
    freq = 440
    num_samples = sample_rate
    buf = bytearray(num_samples * 4)

    for i in range(num_samples):
        val = int(32767 * math.sin(2 * math.pi * freq * i / sample_rate))
        struct.pack_into("<hh", buf, i * 4, val, val)

    dac.write_buffer(buf)
