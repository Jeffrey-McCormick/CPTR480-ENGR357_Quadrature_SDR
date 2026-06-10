import sys
import struct

import asyncio

from dac import DAC
from sd import mount_sd, list_wav_files

FRAME_BYTES = 4  # 16-bit stereo
DRAIN_TAIL_MS = 300  # let the I2S ring empty before muting at EOF
UNMUTE_AFTER_CHUNKS = 2  # small prefill so the ring is buffered before sound


class PlaybackController:
    """
    asyncio-based WAV streamer. play() spawns a task that reads SD chunks
    and feeds them to I2S via StreamWriter.drain(), which yields to other
    tasks (display, encoder, ...) whenever the I2S ring buffer is full.
    """

    STATES = ("stopped", "playing", "paused")

    def __init__(self, sd_mount="/sd", buffer_size=16384):
        self.sd_mount = sd_mount
        # Per-read chunk size. Smaller chunks block the event loop for less
        # time per SD read; larger chunks are slightly more SD-efficient.
        self.buffer_size = buffer_size
        self.dac = None
        self.state = "stopped"
        self.current_file = None
        self.paused = False
        self._file = None
        self._task = None
        self._unmuted = False
        # Generation counter: bumped by stop() so a cancelled stream task
        # never clobbers the state of a newer playback.
        self._gen = 0

    def initialize(self):
        """Mount SD card and initialize the DAC (stereo, muted)."""
        mount_sd(self.sd_mount)
        # No IRQ handler: asyncio drives I2S through the stream interface.
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
        """
        Start playback as an asyncio task. Must be called while the event
        loop is running (e.g. from inside asyncio.run(main())).
        """
        if not self.dac:
            print("PlaybackController not initialized")
            return False

        if self.state == "paused" and self.current_file == filename:
            self.resume()
            return True

        self.stop()

        path = self.sd_mount + "/" + filename
        self._file = open(path, "rb")
        self._skip_to_pcm(self._file)

        self.current_file = filename
        self.paused = False
        self.state = "playing"
        self._unmuted = False
        self._task = asyncio.create_task(self._stream_task(self._gen))
        print(f"Started streaming {filename} (asyncio)")
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
        self._gen += 1
        if self._task:
            self._task.cancel()
            self._task = None
        if self.dac:
            self.dac.mute()
        self._close_file()
        self.state = "stopped"
        self.current_file = None
        self.paused = False
        self._unmuted = False

    def toggle_pause(self):
        """Toggle between playing and paused."""
        if self.state == "playing":
            self.pause()
        elif self.state == "paused":
            self.resume()

    def is_playing(self):
        return self.state == "playing"

    def is_active(self):
        """True while a playback task exists (playing or paused)."""
        return self._task is not None

    async def wait_done(self):
        """Await until the current track finishes (or is stopped)."""
        while self._task is not None:
            await asyncio.sleep_ms(100)

    async def _stream_task(self, gen):
        swriter = asyncio.StreamWriter(self.dac.i2s)
        buf = bytearray(self.buffer_size)
        mv = memoryview(buf)
        chunks = 0

        try:
            while True:
                if self.paused:
                    await asyncio.sleep_ms(20)
                    continue

                nbytes = self._read_pcm_chunk(self._file, buf)
                if nbytes <= 0:
                    break

                swriter.write(mv[:nbytes])
                # Yields here until the I2S ring accepts the whole chunk;
                # display/UI tasks run during this await.
                await swriter.drain()

                chunks += 1
                if not self._unmuted and chunks >= UNMUTE_AFTER_CHUNKS:
                    self.dac.unmute()
                    self._unmuted = True

            # Natural EOF: let the ring play out before muting.
            await asyncio.sleep_ms(DRAIN_TAIL_MS)

        except asyncio.CancelledError:
            pass  # stop() cancelled us; it already cleaned up
        except Exception as e:
            sys.stderr.write(f"Playback error: {e}\n")
        finally:
            if gen == self._gen:
                if self.dac:
                    self.dac.mute()
                self._close_file()
                self.state = "stopped"
                self.current_file = None
                self.paused = False
                self._unmuted = False
                self._task = None

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
