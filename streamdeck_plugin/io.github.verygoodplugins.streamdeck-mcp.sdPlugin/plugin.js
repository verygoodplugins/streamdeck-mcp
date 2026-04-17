/**
 * streamdeck-mcp plugin
 *
 * The plugin is a minimal shell. Its only job is to declare encoder support on
 * behalf of a no-op action so that the Elgato Stream Deck app accepts per-instance
 * Encoder.Icon and Encoder.background fields written directly into the profile
 * manifest by streamdeck-mcp's profile writer. All rendering happens via those
 * manifest fields; this file just registers with the Stream Deck WebSocket and
 * otherwise stays out of the way.
 *
 * See https://docs.elgato.com/streamdeck/sdk/ for the authoritative SDK docs.
 */

function connectElgatoStreamDeckSocket(port, uuid, registerEvent, _info) {
    const ws = new WebSocket("ws://127.0.0.1:" + port);
    ws.onopen = () => {
        ws.send(JSON.stringify({ event: registerEvent, uuid }));
    };
    // willAppear / dialRotate / dialPress / keyDown / keyUp: intentional no-op.
}

window.connectElgatoStreamDeckSocket = connectElgatoStreamDeckSocket;
