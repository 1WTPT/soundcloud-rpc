const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '..', 'reader.js'), 'utf8');

function read({host='soundcloud.com', playing=true, fallback=false,
    css='https://i1.sndcdn.com/cover.jpg', art=null, probeOk=true,
    position='0:16', duration='2:06'} = {}) {
    const link = {getAttribute: () => 'Song', textContent: 'Song', href: 'https://soundcloud.com/a/song'};
    const badge = {querySelector: selector => selector.includes('titleLink') ? link :
        selector.includes('lightLink') ? {getAttribute: () => 'Artist'} : {}};
    return vm.runInNewContext(script, {
        URL,
        window: {},
        Image: class {
            set src(value) { this.naturalWidth = probeOk ? 500 : 0;
                if (probeOk) this.onload(); else this.onerror(); }
        },
        location: {protocol: 'https:', hostname: host},
        navigator: {mediaSession: {metadata: {title: 'Fallback', artist: 'Fallback artist',
            artwork: art || (fallback ? [{src: 'https://i1.sndcdn.com/fallback.jpg'}] : [])}, playbackState: 'playing'}},
        document: {querySelector: selector => selector.includes('timePassed') ? {textContent:position} :
            selector.includes('__duration') ? {textContent:duration} : fallback ? null :
            selector === '.playbackSoundBadge' ? badge : {classList: {contains: () => playing}}},
        getComputedStyle: () => ({backgroundImage: `url("${css}")`})
    });
}

test('reads the playing track rather than the page currently being browsed', () => {
    const result = read();
    assert.equal(result.title, 'Song');
    assert.equal(result.artist, 'Artist');
    assert.equal(result.artwork, 'https://i1.sndcdn.com/cover.jpg');
    assert.equal(result.playing, true);
});
test('pause clears activity', () => assert.equal(read({playing: false}).playing, false));
test('other origins are ignored', () => assert.equal(read({host: 'example.com'}), null));
test('Media Session fallback', () => {
    const result = read({fallback: true});
    assert.equal(result.title, 'Fallback');
    assert.equal(result.artwork, 'https://i1.sndcdn.com/fallback.jpg');
    assert.equal(result.url, '');
});
test('upgrades a tiny cover only after the 500px image loads', () => {
    assert.equal(read({css:'https://i1.sndcdn.com/artworks-abc-t50x50.jpg'}).artwork,
        'https://i1.sndcdn.com/artworks-abc-t500x500.jpg');
});
test('keeps original cover when the larger image fails', () => {
    const css='https://i1.sndcdn.com/artworks-abc-large.jpg';
    assert.equal(read({css,probeOk:false}).artwork,css);
});
test('prefers highest-resolution Media Session image without downgrading', () => {
    const art=[{src:'https://i1.sndcdn.com/high-t1080x1080.jpg',sizes:'1080x1080'},
        {src:'https://i1.sndcdn.com/low-t50x50.jpg',sizes:'50x50'}];
    assert.equal(read({art}).artwork,art[0].src);
});
test('reads elapsed and total seconds for Discord time bar', () => {
    const result=read();
    assert.equal(result.position,16);
    assert.equal(result.duration,126);
});
test('supports hour-long tracks and ignores unknown time', () => {
    assert.equal(read({duration:'1:02:03'}).duration,3723);
    assert.equal(read({duration:'LIVE'}).duration,null);
});
