import sys
import struct
import time
import _thread

from dac import DAC
from sd import mount_sd, list_wav_files

FRAME_BYTES = 4  # 16-bit stereo
NUM_BUFFERS = 4
PREFILL_CHUNKS = 3


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
        self._writer_active = False
        self._read_done = False
        self._file = None
        self._buffers = None
        self._free_slots = []
        self._ready_queue = []
        self._queue_lock = _thread.allocate_lock()

    def initialize(self):
        """Mount SD card and initialize the DAC (stereo, muted)."""
        mount_sd(self.sd_mount)
        self.dac = DAC(nonblocking=False)
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
        """Start playback. SD reads happen on core 0 via pump()."""
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
        self._buffers = [bytearray(self.buffer_size) for _ in range(NUM_BUFFERS)]
        self._free_slots = list(range(NUM_BUFFERS))
        self._ready_queue = []

        path = self.sd_mount + "/" + filename
        self._file = open(path, "rb")
        self._skip_to_pcm(self._file)

        # RP2040 has one spare core: writer thread only. SD reads stay on
        # core 0 via pump() so we never need a second thread for the card.
        try:
            _thread.start_new_thread(self._writer, ())
            print(f"Started streaming {filename}")
            return True
        except OSError:
            print("Second core busy, using blocking playback")
            self._blocking_playback()
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
        self._read_done = True
        self._close_file()

        for _ in range(100):
            if not self._writer_active:
                break
            time.sleep_ms(10)

        if self.dac:
            self.dac.mute()
        self.state = "stopped"
        self.current_file = None
        self.paused = False
        self._buffers = None
        self._ready_queue = []
        self._free_slots = []

    def toggle_pause(self):
        """Toggle between playing and paused."""
        if self.state == "playing":
            self.pause()
        elif self.state == "paused":
            self.resume()

    def is_playing(self):
        return self.state == "playing"

    def is_active(self):
        """True while the writer thread is running or SD reads are pending."""
        return self._writer_active or (self.is_running and not self._read_done)

    def pump(self):
        """
        Read SD on core 0 while the writer feeds I2S on core 1. Fills every
        free buffer slot each call so the main loop keeps the pipeline full.
        """
        if not self.is_running or self.paused or self._read_done:
            return self.is_active()

        while True:
            slot = self._take_free_slot()
            if slot is None:
                break

            try:
                nbytes = self._read_pcm_chunk(self._file, self._buffers[slot])
            except Exception as e:
                sys.stderr.write(f"Pump error: {e}\n")
                self._return_free_slot(slot)
                self._read_done = True
                self._close_file()
                break

            if nbytes <= 0:
                self._return_free_slot(slot)
                self._read_done = True
                self._close_file()
                break

            self._enqueue_ready(slot, nbytes)

        return self.is_active()

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

    def _take_free_slot(self):
        self._queue_lock.acquire()
        try:
            if self._free_slots:
                return self._free_slots.pop(0)
            return None
        finally:
            self._queue_lock.release()

    def _return_free_slot(self, slot):
        self._queue_lock.acquire()
        try:
            self._free_slots.append(slot)
        finally:
            self._queue_lock.release()

    def _enqueue_ready(self, slot, nbytes):
        self._queue_lock.acquire()
        try:
            self._ready_queue.append((slot, nbytes))
        finally:
            self._queue_lock.release()

    def _dequeue_ready(self):
        self._queue_lock.acquire()
        try:
            if self._ready_queue:
                return self._ready_queue.pop(0)
            return None
        finally:
            self._queue_lock.release()

    def _ready_count(self):
        self._queue_lock.acquire()
        try:
            return len(self._ready_queue)
        finally:
            self._queue_lock.release()

    def _writer(self):
        """I2S output on core 1. Never touches the SD card."""
        self._writer_active = True
        unmuted = False

        try:
            while True:
                if not self.is_running and self._read_done and self._ready_count() == 0:
                    break

                if self.paused:
                    time.sleep_ms(5)
                    continue

                if not unmuted:
                    if self._ready_count() < PREFILL_CHUNKS:
                        if self._read_done:
                            break
                        continue
                    self.dac.unmute()
                    unmuted = True

                chunk = self._dequeue_ready()
                if chunk is None:
                    if self._read_done and self._ready_count() == 0:
                        break
                    time.sleep_ms(1)
                    continue

                slot, nbytes = chunk
                self.dac.write_buffer(self._buffers[slot], nbytes)
                self._return_free_slot(slot)

        except Exception as e:
            sys.stderr.write(f"Writer error: {e}\n")
        finally:
            self.is_running = False
            self._writer_active = False
            self._read_done = True
            self._close_file()
            self.state = "stopped"
            self.current_file = None
            self.paused = False
            if self.dac:
                self.dac.mute()
            _thread.exit()

    def _blocking_playback(self):
        """Fallback when core 1 is unavailable: read and write on core 0."""
        self._writer_active = True
        buf = self._buffers[0]

        try:
            for _ in range(PREFILL_CHUNKS):
                nbytes = self._read_pcm_chunk(self._file, buf)
                if nbytes <= 0:
                    return
                self.dac.write_buffer(buf, nbytes)

            self.dac.unmute()

            while self.is_running:
                if self.paused:
                    time.sleep_ms(5)
                    continue

                nbytes = self._read_pcm_chunk(self._file, buf)
                if nbytes <= 0:
                    break
                self.dac.write_buffer(buf, nbytes)

        except Exception as e:
            sys.stderr.write(f"Playback error: {e}\n")
        finally:
            self.is_running = False
            self._writer_active = False
            self._read_done = True
            self._close_file()
            self.state = "stopped"
            self.current_file = None
            self.paused = False
            if self.dac:
                self.dac.mute()
