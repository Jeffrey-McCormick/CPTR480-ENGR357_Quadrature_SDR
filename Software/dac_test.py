import math
import array
import time
from dac import DAC

# Hardware pins
BCK_PIN = 15
WS_PIN = 16
DATA_PIN = 14
MUTE_PIN = 6

SAMPLE_RATE = 44100

def play_tone(audio_out, frequency, sample_rate, duration_seconds, volume=0.2):
    """
    Generates and streams a sine wave in small 8KB chunks to prevent MemoryErrors.
    """
    chunk_samples = 4096  # Small buffer size that easily fits in the Pico's RAM
    amplitude = int(32767 * volume)
    total_samples = int(sample_rate * duration_seconds)
    
    # Pre-allocate a single small reusable array
    buf = array.array('h', [0] * chunk_samples)
    
    samples_generated = 0
    
    while samples_generated < total_samples:
        # Determine how many samples to write this loop (handles the final uneven chunk)
        current_chunk = min(chunk_samples, total_samples - samples_generated)
        
        # Calculate the math for this specific chunk of time
        for i in range(current_chunk):
            t = (samples_generated + i) / sample_rate
            buf[i] = int(amplitude * math.sin(2 * math.pi * frequency * t))
            
        # Stream the filled buffer to the DAC
        if current_chunk == chunk_samples:
            audio_out.write_buffer(buf)
        else:
            audio_out.write_buffer(buf[:current_chunk])
            
        samples_generated += current_chunk

def run_test():
    print("Initializing DAC...")
    audio_out = DAC()

    # Set to Mono for this test
    audio_out.set_mono()
    audio_out.unmute()
    print("Hardware unmuted.")
    
    test_frequencies = [440, 880, 1046, 2000] 
    tone_duration = 1.0 
    
    while True:
        for freq in test_frequencies:
            print(f"Playing {freq} Hz...")
            play_tone(audio_out, freq, SAMPLE_RATE, tone_duration, volume=0.2)
            time.sleep(0.2)

    print("Test complete. Muting and closing DAC.")
    audio_out.close()

if __name__ == "__main__":
    run_test()