"""8-bit sound effects (optional, non-core)."""

import os
import struct
import subprocess
import tempfile
import threading
import wave


class SoundFX:
    def __init__(self):
        self.enabled = True

    def _play(self, freqs, duration_ms=100, volume=0.025):
        if not self.enabled:
            return
        try:
            sample_rate = 22050
            total_samples = int(sample_rate * duration_ms / 1000)
            samples_per_freq = total_samples // len(freqs)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                tmp_path = f.name
            with wave.open(tmp_path, 'w') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                for freq in freqs:
                    for i in range(samples_per_freq):
                        val = int(volume * 32767 * (1 if (i * 2 * freq / sample_rate) % 2 < 1 else -1))
                        wav.writeframesraw(struct.pack('<h', val))
            subprocess.run(['paplay', tmp_path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.unlink(tmp_path)
        except Exception:
            pass

    def power_on(self):
        threading.Thread(target=lambda: self._play([262, 330, 392, 523], 400), daemon=True).start()

    def ding(self):
        threading.Thread(target=lambda: self._play([880, 1100], 150), daemon=True).start()

    def error(self):
        threading.Thread(target=lambda: self._play([220, 185], 200), daemon=True).start()

    def level_complete(self):
        threading.Thread(target=lambda: self._play([523, 659, 784, 1047], 600), daemon=True).start()

    def click(self):
        threading.Thread(target=lambda: self._play([440], 50, 0.15), daemon=True).start()


sfx = SoundFX()
