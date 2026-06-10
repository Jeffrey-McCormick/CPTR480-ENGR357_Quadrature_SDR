import sys
import struct
import time

from dac import DAC
from sd import mount_sd, list_wav_files

FRAME_BYTES = 4  # 16-bit stereo
DRAIN_TAIL_MS = 500
UNMUTE_BYTES = 8192  # ~46 ms stereo @ 44.1 kHz; avoid long mute during SD prefill

_EMPTY = 0
_FULL = 1


class PlaybackController:
    STATES = ("stopped", "playing", "paused")

    def __init__(self, sd_mount="/sd", buffer_size=32768):
        self.sd_mount = sd_mount
        self.buffer_size = buffer_size
        self.dac = None
        self.state = "stopped"
        self.current_file = None
        self.paused = False
        self.is_running = False
        self._read_done = False
        self._unmuted = False
        self._i2s_bytes_out = 0
        self._eof_at = None
        self._file = None
        # Ping-pong double buffer: two halves with strict ownership.
        # The producer (SD read) fills any _EMPTY half; the consumer
        # (I2S feed) drains the current _FULL play half, then swaps.
        self._buf = None
        self._len = [0, 0]
        self._status = [_EMPTY, _EMPTY]
        self._play = 0
        self._play_off = 0

    def initialize(self):
        """Mount SD card and initialize the DAC (stereo, muted)."""
        mount_sd(self.sd_mount)
        # Blocking I2S writes: pump() interleaves SD reads with draining, so
        # partial non-blocking writes are unnecessary and easy to starve.
        self.dac = DAC(nonblocking=False)
        self.dac.set_stereo()
        # Pure polled: pump() drives both SD reads and I2S feeding, so we
        # intentionally do NOT register an IRQ drain handler. This keeps the
        # ping-pong handoff single-threaded and free of IRQ races.
        self.dac.set_drain_handler(None)

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
        """Start playback. pump() reads SD and feeds I2S from the main loop."""
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
        self.is_running = True
        self._read_done = False
        self._unmuted = False
        self._i2s_bytes_out = 0
        self._eof_at = None

        self._buf = [bytearray(self.buffer_size), bytearray(self.buffer_size)]
        self._len = [0, 0]
        self._status = [_EMPTY, _EMPTY]
        self._play = 0
        self._play_off = 0

        path = self.sd_mount + "/" + filename
        self._file = open(path, "rb")
        self._skip_to_pcm(self._file)
        print(f"Started streaming {filename} (ping-pong double buffer)")
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
        if self.dac and self._unmuted:
            self.dac.unmute()

    def stop(self):
        """Halt playback, mute output, and clear the current track."""
        self.is_running = False
        self._read_done = True
        self._close_file()

        if self.dac:
            self.dac.mute()
        self.state = "stopped"
        self.current_file = None
        self.paused = False
        self._unmuted = False
        self._i2s_bytes_out = 0
        self._eof_at = None
        self._buf = None
        self._len = [0, 0]
        self._status = [_EMPTY, _EMPTY]
        self._play = 0
        self._play_off = 0

    def toggle_pause(self):
        """Toggle between playing and paused."""
        if self.state == "playing":
            self.pause()
        elif self.state == "paused":
            self.resume()

    def is_playing(self):
        return self.state == "playing"

    def is_active(self):
        """True while reading, or while either half still holds audio to drain."""
        if self.is_running and not self._read_done:
            return True
        if self._status[0] == _FULL or self._status[1] == _FULL:
            return True
        if self._eof_at is not None:
            return time.ticks_diff(time.ticks_ms(), self._eof_at) < DRAIN_TAIL_MS
        return False

    def pump(self):
        """
        Drive playback from the main loop: fill empty halves from SD and
        drain the current play half into the I2S ring. Call this often.
        """
        if not self.is_running:
            return False

        if self.paused:
            return self.is_active()

        # Drain I2S before reading SD so a slow card read cannot starve output.
        self._drain()
        self._fill()
        self._maybe_finish()
        return self.is_active()

    def _fill(self):
        """Producer: read one SD chunk into a single _EMPTY half per pump()."""
        if self._read_done:
            return

        idx = self._empty_half()
        if idx is None:
            return

        try:
            nbytes = self._read_pcm_chunk(self._file, self._buf[idx])
        except Exception as e:
            sys.stderr.write(f"Fill error: {e}\n")
            self._read_done = True
            self._close_file()
            return

        if nbytes <= 0:
            self._read_done = True
            self._close_file()
            return

        self._len[idx] = nbytes
        self._status[idx] = _FULL

    def _drain(self):
        """Consumer: push the current play half into the non-blocking I2S ring."""
        if not self.dac or self.paused:
            return

        while self._status[self._play] == _FULL:
            view = memoryview(self._buf[self._play])[self._play_off:self._len[self._play]]
            if len(view) == 0:
                self._swap_play_half()
                continue

            written = self.dac.write(view)
            if written <= 0:
                break  # I2S ring is full; try again next pump()

            self._play_off += written
            self._i2s_bytes_out += written
            if self._play_off >= self._len[self._play]:
                self._swap_play_half()

        if not self._unmuted and self._i2s_bytes_out >= UNMUTE_BYTES:
            self.dac.unmute()
            self._unmuted = True

    def _swap_play_half(self):
        """Release the drained half back to the producer and ping-pong over."""
        self._status[self._play] = _EMPTY
        self._len[self._play] = 0
        self._play_off = 0
        self._play ^= 1

    def _empty_half(self):
        if self._status[0] == _EMPTY:
            return 0
        if self._status[1] == _EMPTY:
            return 1
        return None

    def _maybe_finish(self):
        if not self._read_done:
            return
        if self._status[0] == _FULL or self._status[1] == _FULL:
            self._eof_at = None
            return
        if self._eof_at is None:
            self._eof_at = time.ticks_ms()
            return
        if time.ticks_diff(time.ticks_ms(), self._eof_at) >= DRAIN_TAIL_MS:
            self.is_running = False
            self.state = "stopped"
            self.current_file = None
            self.paused = False
            if self.dac:
                self.dac.mute()
            self._unmuted = False

    def _close_file(self):
        if self._file:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None

    def _skip_to_pcm(self, f):
        """Seek past the WAV header to the start of PCM sample data."""
        if f.read(4) != b"RIFF":
            raise ValueError("Not a WAV file")

        f.read(4)

        if f.read(4) != b"WAVE":
            raise ValueError("Not a WAVE file")

        while True:
            chunk_hdr = f.read(8)
            if len(chunk_hdr) < 8:
                raise ValueError("WAV data chunk not found")

            chunk_id, chunk_size = struct.unpack("<4sI", chunk_hdr)
            if chunk_id == b"data":
                return

            f.seek(chunk_size, 1)

    def _read_pcm_chunk(self, f, buf):
        """Read the next aligned stereo PCM chunk into buf. Returns byte count."""
        nbytes = f.readinto(buf)
        if nbytes <= 0:
            return 0
        return nbytes & ~(FRAME_BYTES - 1)
