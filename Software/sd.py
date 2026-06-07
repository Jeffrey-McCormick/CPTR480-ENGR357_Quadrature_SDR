import math
import os
import struct
from machine import SPI, I2S, Pin

# steps to stream
# 1. init sd card : init_sd()
# 2. list files : list_files()
# 3. init i2s : init_i2s() : optional parameters : bits, rate, ibuf
# 4. stream audio : stream_audio(filename, buffer_size) : optional parameter : buffer_size

SD_CS_PIN = 1
SD_SCK_PIN = 2
SD_MOSI_PIN = 3
SD_MISO_PIN = 0

I2S_BCLK_PIN = 15
I2S_LRCK_PIN = 16
I2S_DIN_PIN = 14

BUFFER_SIZE = 512

def init_i2s(bits=16, rate=44100, ibuf=20480):
    global i2s
    i2s = I2S(0, sck=Pin(I2S_BCLK_PIN), ws=Pin(I2S_LRCK_PIN), sd=Pin(I2S_DIN_PIN), 
               mode=I2S.TX, bits=bits, format=I2S.MONO, rate=rate, ibuf=ibuf)
    print("I2S initialized successfully")

def list_files():
    print("Files on SD Card:")
    for filename in os.listdir("/sd"):
        print(filename)
        
def stream_audio(filename, buffer_size=BUFFER_SIZE):
    try:
        with open("/sd/" + filename, "rb") as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                i2s.write(data)
                # print(data)
    except Exception as e:
        print(f"Error streaming audio: {e}")
        raise

def init_sd():
    try:
        import sdcard
        # Initialize SPI for SD Card
        spi = SPI(0, baudrate=40000000, polarity=0, phase=0, 
                sck=Pin(SD_SCK_PIN), mosi=Pin(SD_MOSI_PIN), miso=Pin(SD_MISO_PIN))
        sd = sdcard.SDCard(spi, Pin(SD_CS_PIN))
        os.mount(sd, "/sd")
        print("SD Card mounted successfully at /sd")
    except ImportError:
        print("Error: 'sdcard.py' library missing! Please upload it to your Pico.")
        raise
    except Exception as e:
        print(f"Failed to mount SD Card: {e}")
        raise
    
if __name__ == "__main__":
    init_sd()
    list_files()
    init_i2s()
    stream_audio("I Thank God_44100.wav")