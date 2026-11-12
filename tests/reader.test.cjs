const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '..', 'reader.js'), 'utf8');

function read({host='soundcloud.com', playing=true, fallback=false} = {}) {
    const link = {getAttribute: () => 'Song', textContent: 'Song', href: 'https://soundcloud.com/a/song'};
    const badge = {querySelector: selector => selector.includes('titleLink') ? link :
        selector.includes('lightLink') ? {getAttribute: () => 'Artist'} : {}};
    return vm.runInNewContext(script, {
        location: {protocol: 'https:', hostname: host},
        navigator: {mediaSession: {metadata: {title: 'Fallback', artist: 'Fallback artist',
            artwork: [{src: 'https://i1.sndcdn.com/fallback.jpg'}]}, playbackState: 'playing'}},
        document: {querySelector: selector => fallback ? null :
            selector === '.playbackSoundBadge' ? badge : {classList: {contains: () => playing}}},
        getComputedStyle: () => ({backgroundImage: 'url("https://i1.sndcdn.com/cover.jpg")'})
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
