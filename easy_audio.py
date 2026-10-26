"""Pitch-preserving tempo processing; playback gain never changes saved audio."""
import math
from pathlib import Path
import shutil
import subprocess
import uuid


def change_speed(source, speed):
    speed = float(speed)
    if not math.isfinite(speed) or not 0.75 <= speed <= 1.5:
        raise ValueError("話速は0.75～1.50倍で指定してください。")
    if speed == 1.0:
        return source
    source = Path(source).resolve()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg が見つかりません。")
    target = source.with_name(f"{source.stem}_speed_{speed:.2f}_{uuid.uuid4().hex[:8]}.wav")
    partial = target.with_suffix(".partial.wav")
    try:
        # atempo preserves pitch and does not apply playback gain or normalization.
        subprocess.run(
            [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
             "-i", str(source), "-map", "0:a:0", "-af", f"atempo={speed:.4f}",
             "-c:a", "pcm_s24le", str(partial)],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        partial.replace(target)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"話速の変更に失敗しました: {exc.stderr}") from exc
    finally:
        partial.unlink(missing_ok=True)
    return str(target)


VOLUME_HTML = """
<label for="easy-volume-slider">再生音量：<output id="easy-volume-value">75</output>％</label>
<input id="easy-volume-slider" type="range" min="0" max="100" step="1" value="75"
 style="width:100%" aria-label="再生音量（WAVの音量は変わりません）">
<p>このブラウザに記憶します。保存するWAVの音量は変更しません。</p>
"""

VOLUME_JS = """() => {
    if (window.easyVolumeCleanup) window.easyVolumeCleanup();
    const key = 'easy-irodori-playback-volume';
    let volume = 0.75;
    try {
        const saved = localStorage.getItem(key);
        const number = Number(saved);
        if (saved !== null && saved.trim() !== '' && Number.isFinite(number)
            && number >= 0 && number <= 1) volume = number;
    } catch (_) { /* Private browsing may disable storage. */ }
    const controller = new AbortController();
    const options = {signal: controller.signal};
    const bound = new WeakSet();
    const sources = new WeakMap();
    const resetPosition = audio => {
        audio.pause();
        try { audio.currentTime = 0; } catch (_) {}
        // Notify Gradio's bound playback state, not just the native audio element.
        audio.dispatchEvent(new Event('timeupdate'));
    };
    document.addEventListener('click', event => {
        if (event.target.closest('#easy-generate-button')) players().forEach(resetPosition);
    }, {capture:true, signal:controller.signal});
    const sliders = new WeakSet();
    const observedRoots = new WeakSet();
    const players = () => {
        const found = [];
        const root = document.getElementById('easy-generated-audio');
        const visit = scope => {
            found.push(...scope.querySelectorAll('audio'));
            scope.querySelectorAll('*').forEach(element => {
                if (!element.shadowRoot) return;
                if (!observedRoots.has(element.shadowRoot)) {
                    observedRoots.add(element.shadowRoot);
                    observer.observe(element.shadowRoot, {
                        childList:true, subtree:true, attributes:true, attributeFilter:['src']
                    });
                }
                visit(element.shadowRoot);
            });
        };
        if (root) visit(root);
        return found;
    };
    const apply = audio => { if (audio.volume !== volume) audio.volume = volume; audio.setAttribute("data-easy-playback-volume", String(audio.volume)); };
    const refresh = () => {
        const slider = document.getElementById('easy-volume-slider');
        if (slider) {
            slider.value = String(Math.round(volume * 100));
            if (!sliders.has(slider)) {
                sliders.add(slider);
                slider.addEventListener('input', () => {
                    volume = Number(slider.value) / 100;
                    try { localStorage.setItem(key, String(volume)); } catch (_) {}
                    players().forEach(apply);
                    refresh();
                }, options);
            }
        }
        const label = document.getElementById('easy-volume-value');
        const text = String(Math.round(volume * 100));
        if (label && label.textContent !== text) label.textContent = text;
        players().forEach(audio => {
            apply(audio);
            const source = audio.getAttribute('src') || audio.querySelector('source')?.getAttribute('src') || '';
            if (sources.get(audio) !== source) { sources.set(audio, source); resetPosition(audio); }
            if (bound.has(audio)) return;
            bound.add(audio);
            audio.addEventListener('loadedmetadata', () => resetPosition(audio), options);
            // Keep the dedicated slider authoritative even when the player resets.
            ['volumechange', 'loadedmetadata', 'play', 'emptied'].forEach(event =>
                audio.addEventListener(event, () => apply(audio), options));
        });
        document.querySelectorAll('#easy-generated-audio button[aria-label="Adjust volume"]')
            .forEach(button => { button.style.display = 'none'; });
    };
    const observer = new MutationObserver(refresh);
    observer.observe(document.body, {childList:true, subtree:true, attributes:true,
                                    attributeFilter:['src']});
    refresh();
    window.easyVolumeCleanup = () => {observer.disconnect(); controller.abort();};
} 
"""
