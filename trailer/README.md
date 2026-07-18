# streamdeck-mcp Trailer

Remotion product trailer for `streamdeck-mcp`.

Composition:

- `StreamDeckTrailer`
- `1920x1080`
- `30fps`
- `1350` frames, about 45 seconds

The UI is simulated in React. It demonstrates profile inventory, installed plugin discovery, configured raw plugin action reuse, icon/script/page writing, and the final Stream Deck + XL profile reveal.

## Commands

Install dependencies:

```console
npm i
```

Generate local audio assets:

```console
npm run generate-audio
```

Start Remotion Studio:

```console
npm run dev
```

Run tests and type/lint checks:

```console
npm test
npm run lint
```

Render checkpoint stills:

```console
npm run still:hook
npm run still:plugins
npm run still:reuse
npm run still:final
```

Render the trailer:

```console
npm run render
```

Output lands at `out/streamdeck-mcp-trailer.mp4`.
