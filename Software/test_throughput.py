import time
from sd import mount_sd, list_wav_files
mount_sd()

buf = bytearray(32768)
total = 0
with open("/sd/" + list_wav_files()[0], "rb") as f:
    t0 = time.ticks_ms()
    while True:
        n = f.readinto(buf)
        if not n:
            break
        total += n
    dt = time.ticks_diff(time.ticks_ms(), t0)

print(total, "bytes in", dt, "ms =", total * 1000 // dt // 1024, "KB/s")