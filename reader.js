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
    const mediaArt = metadata?.artwork?.slice(-1)[0]?.src || '';
    return {
        title: title?.getAttribute('title') || title?.textContent?.trim() || metadata?.title || '',
        artist: artist?.getAttribute('title') || artist?.textContent?.trim() || metadata?.artist || '',
        artwork: background || mediaArt,
        url: title?.href || '',
        playing: play ? play.classList.contains('playing') :
            navigator.mediaSession?.playbackState === 'playing'
    };
})();
