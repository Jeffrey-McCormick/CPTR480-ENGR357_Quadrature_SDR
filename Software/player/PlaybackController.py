import sys
import time
import _thread

from dac import DAC
from sd import mount_sd, list_wav_files


class PlaybackController:
    STATES = ("stopped", "playing", "paused")

    def __init__(self, sd_mount="/sd", buffer_size=512):
        self.sd_mount = sd_mount
        self.buffer_size = buffer_size
        self.dac = None
        self.state = "stopped"
        self.current_file = None
        self.paused = False
        self.is_running = False
        self._thread_active = False

    def initialize(self):
        """Mount SD card and initialize the DAC (stereo, muted)."""
        mount_sd(self.sd_mount)
        self.dac = DAC()
        self.dac.set_stereo()

    def shutdown(self):
        """Stop playback and release DAC hardware."""
        self.stop()
        if self.dac:
            self.dac.close()
            self.dac = None

    def list_tracks(self):
        """Return sorted .wav filenames on the SD card."""
        return list_wav_files(self.sd_mount)

    def play(self, filename):
        """Start or switch to a track. Returns True if playback started."""
        if not self.dac:
            print("PlaybackController not initialized")
            return False

        if self.state == "paused" and self.current_file == filename:
            self.resume()
            return True

        self.stop()

        self.current_file = filename
        self.paused = False
        self.state = "playing"
        _thread.start_new_thread(self._worker, ())
        print(f"Started streaming {filename} on Core 1")
        return True

    def pause(self):
        """Pause playback while keeping the current track."""
        if self.state != "playing":
            return
        self.paused = True
        self.state = "paused"
        if self.dac:
            self.dac.mute()

    def resume(self):
        """Resume a paused track."""
        if self.state != "paused":
            return
        self.paused = False
        self.state = "playing"
        if self.dac:
            self.dac.unmute()

    def stop(self):
        """Halt playback, mute output, and clear the current track."""
        self.is_running = False
        for _ in range(10):
            if not self._thread_active:
                break
            time.sleep_ms(10)

        if self.dac:
            self.dac.mute()
        self.state = "stopped"
        self.current_file = None
        self.paused = False

    def toggle_pause(self):
        """Toggle between playing and paused."""
        if self.state == "playing":
            self.pause()
        elif self.state == "paused":
            self.resume()

    def is_playing(self):
        return self.state == "playing"

    def _worker(self):
        self.is_running = True
        self._thread_active = True
        unmuted = False

        try:
            path = self.sd_mount + "/" + self.current_file
            with open(path, "rb") as f:
                header_buffer = bytearray(4)

                while True:
                    byte = f.read(1)
                    if not byte:
                        break

                    header_buffer[0:3] = header_buffer[1:4]
                    header_buffer[3] = byte[0]

                    if header_buffer == b"data":
                        f.read(4)
                        break

                while self.is_running:
                    if not self.paused:
                        data = f.read(self.buffer_size)
                        if not data:
                            break

                        if not unmuted:
                            self.dac.unmute()
                            unmuted = True
                        self.dac.write_buffer(data)
                    else:
                        time.sleep_ms(20)

        except Exception as e:
            sys.stderr.write(f"Core 1 Error: {e}\n")
        finally:
            self.is_running = False
            self._thread_active = False
            self.state = "stopped"
            self.current_file = None
            self.paused = False
            if self.dac:
                self.dac.mute()
            _thread.exit()
