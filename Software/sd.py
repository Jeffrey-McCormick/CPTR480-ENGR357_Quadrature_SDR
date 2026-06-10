import os
from machine import SPI, Pin
import sdcard

SD_CS_PIN = 1
SD_SCK_PIN = 2
SD_MOSI_PIN = 3
SD_MISO_PIN = 0


def mount_sd(mount_point="/sd"):
    """Mount the SD card over SPI at the given path."""
    try:
        os.umount(mount_point)
    except OSError:
        pass

    try:
        spi = SPI(
            0,
            baudrate=20000000,
            polarity=0,
            phase=0,
            sck=Pin(SD_SCK_PIN),
            mosi=Pin(SD_MOSI_PIN),
            miso=Pin(SD_MISO_PIN),
        )
        sd = sdcard.SDCard(spi, Pin(SD_CS_PIN), baudrate=25000000)
        sd.init_spi(25000000)
        os.mount(sd, mount_point)
        print(f"SD Card mounted successfully at {mount_point}")
    except Exception as e:
        print(f"Failed to mount SD Card: {e}")
        raise


def list_wav_files(mount_point="/sd"):
    """Return sorted .wav filenames from the mounted SD card."""
    return sorted(
        f for f in os.listdir(mount_point)
        if f.lower().endswith(".wav") and not f.startswith("._")
    )


if __name__ == "__main__":
    import sys
    import time
    import asyncio

    sys.path.append("player")
    from PlaybackController import PlaybackController

    time.sleep(2)

    async def main():
        player = PlaybackController()
        player.initialize()

        tracks = player.list_tracks()
        print(f"Found {len(tracks)} track(s): {tracks}")

        if tracks:
            player.play(tracks[0])
            await player.wait_done()

        player.shutdown()

    asyncio.run(main())
