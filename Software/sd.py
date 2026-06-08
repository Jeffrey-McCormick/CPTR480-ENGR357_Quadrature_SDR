import os
import sys
import time
import _thread  # MicroPython dual-core module
from machine import SPI, I2S, Pin

SD_CS_PIN = 1
SD_SCK_PIN = 2
SD_MOSI_PIN = 3
SD_MISO_PIN = 0

I2S_BCLK_PIN = 15
I2S_LRCK_PIN = 16
I2S_DIN_PIN = 14

BUFFER_SIZE = 512

class AudioStreamer:
    def __init__(self, bits=16, rate=44100, ibuf=20480):
        self.i2s = None
        self.init_i2s(bits, rate, ibuf)
        self.paused = False
        self.current_song = None
        self.is_running = False

    def init_i2s(self, bits=16, rate=44100, ibuf=20480):
        self.i2s = I2S(0, sck=Pin(I2S_BCLK_PIN), ws=Pin(I2S_LRCK_PIN), sd=Pin(I2S_DIN_PIN), 
                        mode=I2S.TX, bits=bits, format=I2S.MONO, rate=rate, ibuf=ibuf)
        print("I2S initialized successfully")

    def list_files(self):
        return [f for f in os.listdir("/sd") if f.lower().endswith('.wav')]

    def _audio_thread_worker(self):
        """This function runs entirely on Core 1 in the background."""
        self.is_running = True
        try:
            with open("/sd/" + self.current_song, "rb") as f:
                # --- AUTOMATIC DATA FINDER ---
                header_buffer = bytearray(4)
                
                while True:
                    byte = f.read(1)
                    if not byte:
                        break
                        
                    # Shift all elements left by 1 using slicing
                    header_buffer[0:3] = header_buffer[1:4]
                    header_buffer[3] = byte[0]
                        
                    # Check if our rolling window spells 'data' (0x64, 0x61, 0x74, 0x61)
                    if header_buffer == b'data':
                        f.read(4) # Read size integer to clear data pointer
                        break
                
                # --- RUN THE NORMAL STREAMING LOOP ---
                # Now safely aligned deep within the open file context block
                while self.is_running:
                    if not self.paused:
                        data = f.read(BUFFER_SIZE)
                        if not data:
                            break  # End of file reached
                        
                        self.i2s.write(data)
                        sys.stdout.buffer.write(data)
                    else:
                        time.sleep(0.02)
                        
        except Exception as e:
            sys.stderr.write(f"Core 1 Error: {e}\n")
        finally:
            self.is_running = False
            _thread.exit()

    def start_stream(self, filename):
        """Spawns the streaming loop thread onto Core 1."""
        if self.is_running:
            print("Audio is already playing!")
            return
        
        self.current_song = filename
        _thread.start_new_thread(self._audio_thread_worker, ())
        print(f"Started streaming {filename} on Core 1")

    def stop_stream(self):
        """Safely terminates the background thread loop."""
        self.is_running = False

    def init_sd(self):
        try:
            import sdcard
            spi = SPI(0, baudrate=20000000, polarity=0, phase=0, 
                    sck=Pin(SD_SCK_PIN), mosi=Pin(SD_MOSI_PIN), miso=Pin(SD_MISO_PIN))
            sd = sdcard.SDCard(spi, Pin(SD_CS_PIN))
            os.mount(sd, "/sd")
            print("SD Card mounted successfully at /sd")
        except Exception as e:
            print(f"Failed to mount SD Card: {e}")
            raise
        
if __name__ == "__main__":
    time.sleep(2)  # Short pause to give USB link stability
    
    streamer = AudioStreamer()
    streamer.init_sd()
    streamer.init_i2s()
    songs = streamer.list_files()
    streamer.start_stream(songs[0])  
    time.sleep(5)
    streamer.stop_stream()