import math
import os
import random
import struct
import wave

AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "app", "static", "audio"
)
os.makedirs(AUDIO_DIR, exist_ok=True)
WAV_PATH = os.path.join(AUDIO_DIR, "ocean_waves.wav")


def generate_ocean_waves_wav():
    sample_rate = 22050
    duration_sec = 7.0
    num_samples = int(sample_rate * duration_sec)

    # Low-pass / band-pass state variables for left & right channels (brown/pink surf noise)
    lp_l1, lp_l2 = 0.0, 0.0
    lp_r1, lp_r2 = 0.0, 0.0
    foam_l, foam_r = 0.0, 0.0

    random.seed(2026)
    frames = bytearray()

    for i in range(num_samples):
        t = i / sample_rate

        # Overall fade-in (0..0.6s) and fade-out (5.8..7.0s)
        if t < 0.6:
            master_env = t / 0.6
        elif t > 5.8:
            master_env = max(0.0, (duration_sec - t) / 1.2)
        else:
            master_env = 1.0

        # Two big rolling ocean wave crests (around t=1.4s and t=4.2s) + swimmer dive splash at t=0.45s
        wave1 = math.exp(-((t - 1.55) ** 2) / 0.85)
        wave2 = math.exp(-((t - 4.35) ** 2) / 1.05)
        dive_splash = math.exp(-((t - 0.52) ** 2) / 0.045) * 0.85

        swell_env = 0.22 + 0.68 * max(wave1, wave2) + dive_splash

        # White noise source
        wn_l = random.uniform(-1.0, 1.0)
        wn_r = random.uniform(-1.0, 1.0)

        # Dynamic cutoff frequency rises as the wave crests break into whitewater foam
        alpha_deep = 0.045 + 0.075 * swell_env
        lp_l1 += alpha_deep * (wn_l - lp_l1)
        lp_l2 += alpha_deep * (lp_l1 - lp_l2)

        lp_r1 += alpha_deep * (wn_r - lp_r1)
        lp_r2 += alpha_deep * (lp_r1 - lp_r2)

        # High-frequency surf hiss / sea spray on wave crest
        alpha_foam = 0.24 + 0.25 * (wave1 + wave2 + dive_splash)
        foam_l += alpha_foam * (wn_l - foam_l)
        foam_r += alpha_foam * (wn_r - foam_r)
        spray_l = (wn_l - foam_l) * (0.18 * (wave1 + wave2) + 0.35 * dive_splash)
        spray_r = (wn_r - foam_r) * (0.18 * (wave1 + wave2) + 0.35 * dive_splash)

        # Subtle underwater hydro-bubble resonance
        bubble_freq = 320.0 + 90.0 * math.sin(t * 9.5)
        bubble_env = max(0.0, math.sin(t * 7.2) ** 8) * 0.045
        bubble_sig = math.sin(2.0 * math.pi * bubble_freq * t) * bubble_env

        left = (lp_l2 * 1.45 * swell_env + spray_l + bubble_sig) * master_env
        right = (lp_r2 * 1.45 * swell_env + spray_r - bubble_sig * 0.6) * master_env

        # Soft clip & convert to 16-bit PCM
        left_pcm = int(max(-0.95, min(0.95, left)) * 32767)
        right_pcm = int(max(-0.95, min(0.95, right)) * 32767)
        frames.extend(struct.pack("<hh", left_pcm, right_pcm))

    with wave.open(WAV_PATH, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))

    print(f"[SUCCESS] Generated stereo ocean waves audio: {WAV_PATH} ({os.path.getsize(WAV_PATH)} bytes)")


def generate_water_select_wav():
    """Generates a refreshing, crisp water droplet & cool crystal chime when selecting products/options."""
    sample_rate = 22050
    duration_sec = 0.36
    num_samples = int(sample_rate * duration_sec)
    out_path = os.path.join(AUDIO_DIR, "water_select.wav")
    frames = bytearray()
    phase1 = 0.0
    phase2 = 0.0

    for i in range(num_samples):
        t = i / sample_rate
        # Pitch-swept water droplet (starts at 520Hz and sweeps up to 1180Hz like a crisp bubble)
        freq1 = 520.0 + 1850.0 * min(1.0, (t / 0.14) ** 1.4)
        env1 = math.exp(-t * 16.0) * min(1.0, t / 0.008)
        phase1 += 2.0 * math.pi * freq1 / sample_rate

        # Soft cool aqua harmonic chime (E6 = 1318.5Hz)
        freq2 = 1318.5
        env2 = math.exp(-max(0.0, t - 0.03) * 11.0) * (1.0 if t >= 0.03 else 0.0)
        phase2 += 2.0 * math.pi * freq2 / sample_rate

        sig_l = math.sin(phase1) * env1 * 0.42 + math.sin(phase2) * env2 * 0.24
        sig_r = math.sin(phase1 * 1.003) * env1 * 0.40 + math.cos(phase2) * env2 * 0.26

        l_pcm = int(max(-0.95, min(0.95, sig_l)) * 32767)
        r_pcm = int(max(-0.95, min(0.95, sig_r)) * 32767)
        frames.extend(struct.pack("<hh", l_pcm, r_pcm))

    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))
    print(f"[SUCCESS] Generated refreshing product select audio: {out_path} ({os.path.getsize(out_path)} bytes)")


def generate_order_celebration_wav():
    """Generates a joyful, uplifting celebration chime fanfare when an order/purchase succeeds."""
    sample_rate = 22050
    duration_sec = 1.85
    num_samples = int(sample_rate * duration_sec)
    out_path = os.path.join(AUDIO_DIR, "order_celebration.wav")
    frames = bytearray()

    # Joyful ascending C Major 9th arpeggio + final sparkling chord: C5, E5, G5, B5, D6, G6
    notes = [
        (0.00, 523.25, 0.45),   # C5
        (0.11, 659.25, 0.45),   # E5
        (0.22, 783.99, 0.48),   # G5
        (0.33, 987.77, 0.52),   # B5
        (0.45, 1046.50, 1.30),  # C6 (sustained celebration chord)
        (0.45, 1318.51, 1.30),  # E6
        (0.45, 1567.98, 1.35),  # G6
    ]

    for i in range(num_samples):
        t = i / sample_rate
        sig_l = 0.0
        sig_r = 0.0
        for start_t, freq, dur in notes:
            if t >= start_t:
                dt = t - start_t
                if dt < dur:
                    attack = min(1.0, dt / 0.012)
                    decay = math.exp(-dt * 3.2)
                    env = attack * decay
                    # Bell-like FM synthesis + overtone
                    tone = math.sin(2.0 * math.pi * freq * dt + 0.35 * math.sin(4.0 * math.pi * freq * dt) * math.exp(-dt * 8.0))
                    overtone = 0.25 * math.sin(2.0 * math.pi * (freq * 2.0) * dt) * math.exp(-dt * 6.0)
                    sig_l += (tone + overtone) * env * 0.22
                    sig_r += (tone * 0.96 + overtone * 1.05) * env * 0.22

        l_pcm = int(max(-0.95, min(0.95, sig_l)) * 32767)
        r_pcm = int(max(-0.95, min(0.95, sig_r)) * 32767)
        frames.extend(struct.pack("<hh", l_pcm, r_pcm))

    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))
    print(f"[SUCCESS] Generated order celebration audio: {out_path} ({os.path.getsize(out_path)} bytes)")


if __name__ == "__main__":
    generate_ocean_waves_wav()
    generate_water_select_wav()
    generate_order_celebration_wav()

