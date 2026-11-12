// Evaluated by the host. No extension, Python bridge, HTTP server or site API key.
(() => {
    if (location.protocol !== 'https:' ||
        !['soundcloud.com', 'www.soundcloud.com'].includes(location.hostname)) {
        return null;
    }
    const badge = document.querySelector('.playbackSoundBadge');
    const title = badge?.querySelector('.playbackSoundBadge__titleLink');
    const artist = badge?.querySelector('.playbackSoundBadge__lightLink');
    const image = badge?.querySelector('.sc-artwork');
    const metadata = navigator.mediaSession?.metadata;
    const play = document.querySelector('.playControls__play');
    const css = image ? getComputedStyle(image).backgroundImage : '';
    const background = css.match(/url\(["']?(.*?)["']?\)/)?.[1] || '';
    const artSize = entry => Number.parseInt(entry.sizes, 10) || 0;
    const mediaArt = metadata?.artwork?.slice().sort((a, b) => artSize(b) - artSize(a))[0]?.src || '';
    // The mini-player usually contains a tiny thumbnail. Test the 500px CDN
    // variant once per image and retain the source if the larger one is absent.
    const sourceArt = mediaArt || background;
    let artwork = sourceArt;
    try {
        const url = new URL(sourceArt);
        if (url.protocol === 'https:' && url.hostname.endsWith('.sndcdn.com')) {
            const larger = new URL(url);
            larger.pathname = larger.pathname.replace(
                /-(?:large|small|badge|tiny|t(?:20|50|60|67|80|100|120|200|240|250|300)x\d+)(?=\.[a-z]+$)/i,
                '-t500x500');
            if (larger.href !== url.href) {
                const cache = window.__soundcloudRpcArtworkCache ||= new Map();
                let entry = cache.get(sourceArt);
                if (!entry) {
                    if (cache.size >= 32) cache.delete(cache.keys().next().value);
                    entry = {url: sourceArt};
                    cache.set(sourceArt, entry);
                    const probe = new Image();
                    probe.onload = () => { if (probe.naturalWidth >= 500) entry.url = larger.href; };
                    probe.onerror = () => {}; // Keep the original working image.
                    probe.src = larger.href;
                }
                artwork = entry.url;
            }
        }
    } catch (_) { /* Empty or non-URL artwork: Python validation handles it. */ }
    const seconds = selector => {
        const element = document.querySelector(selector);
        const parts = element?.textContent?.trim().split(':');
        if (!parts || parts.length < 2 || parts.length > 3 ||
            !parts.every(p => /^\d+$/.test(p))) return null;
        return parts.reduce((total, p) => total * 60 + Number(p), 0);
    };
    return {
        title: title?.getAttribute('title') || title?.textContent?.trim() || metadata?.title || '',
        artist: artist?.getAttribute('title') || artist?.textContent?.trim() || metadata?.artist || '',
        artwork,
        position: seconds('.playbackTimeline__timePassed span[aria-hidden="true"]'),
        duration: seconds('.playbackTimeline__duration span[aria-hidden="true"]'),
        url: title?.href || '',
        playing: play ? play.classList.contains('playing') :
            navigator.mediaSession?.playbackState === 'playing'
    };
})();
