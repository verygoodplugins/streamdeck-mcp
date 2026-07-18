export const trailerConfig = {
  id: "StreamDeckTrailer",
  fps: 30,
  width: 1920,
  height: 1080,
  durationInFrames: 1350,
} as const;

export type SceneId =
  | "hook"
  | "inventory"
  | "plugin-scan"
  | "raw-action-reuse"
  | "icon-script-write"
  | "final-reveal";

export type SceneSpec = {
  id: SceneId;
  from: number;
  duration: number;
  eyebrow: string;
  headline: string;
};

export const scenes: SceneSpec[] = [
  {
    id: "hook",
    from: 0,
    duration: 210,
    eyebrow: "streamdeck-mcp",
    headline: "Tell your AI what Stream Deck you want.",
  },
  {
    id: "inventory",
    from: 210,
    duration: 210,
    eyebrow: "streamdeck_read_profiles",
    headline: "It starts with your actual hardware.",
  },
  {
    id: "plugin-scan",
    from: 420,
    duration: 210,
    eyebrow: "streamdeck_read_plugins",
    headline: "Installed plugins become usable context.",
  },
  {
    id: "raw-action-reuse",
    from: 630,
    duration: 240,
    eyebrow: "streamdeck_read_page -> streamdeck_write_page",
    headline: "Existing plugin actions can move without losing settings.",
  },
  {
    id: "icon-script-write",
    from: 870,
    duration: 180,
    eyebrow: "icons + scripts + manifests",
    headline: "The profile is written in one clean pass.",
  },
  {
    id: "final-reveal",
    from: 1050,
    duration: 300,
    eyebrow: "final profile",
    headline: "A polished control board, authored from a prompt.",
  },
];

export type PluginEntry = {
  name: string;
  uuid: string;
  actionCount: number;
  controllers: string[];
  color: string;
};

export const installedPlugins: PluginEntry[] = [
  {
    name: "Home Assistant",
    uuid: "de.perdoctus.streamdeck.homeassistant",
    actionCount: 2,
    controllers: ["Keypad", "Encoder"],
    color: "#22d3ee",
  },
  {
    name: "Wave Link",
    uuid: "com.elgato.wave-link",
    actionCount: 8,
    controllers: ["Encoder"],
    color: "#a78bfa",
  },
  {
    name: "Spotify",
    uuid: "com.spotify.streamdeck",
    actionCount: 5,
    controllers: ["Keypad"],
    color: "#34d399",
  },
  {
    name: "GitHub Utilities",
    uuid: "com.elgato.github-utilities",
    actionCount: 4,
    controllers: ["Keypad"],
    color: "#fbbf24",
  },
  {
    name: "streamdeck-mcp",
    uuid: "io.github.verygoodplugins.streamdeck-mcp",
    actionCount: 7,
    controllers: ["Encoder"],
    color: "#2dd4bf",
  },
];

export type RawPluginAction = {
  ActionID: string;
  LinkedTitle: boolean;
  Name: string;
  Plugin: {
    Name: string;
    UUID: string;
    Version: string;
  };
  Settings: {
    entityId: string;
    mode: string;
  };
  State: number;
  States: Array<{
    Title: string;
    Image: string;
  }>;
  UUID: string;
};

export type PageButton = {
  controller: "keypad" | "encoder";
  key: number;
  position: string;
  title: string;
  plugin_uuid: string;
  action_uuid: string;
  settings: RawPluginAction["Settings"];
  raw: RawPluginAction;
};

export const sourcePluginButton: PageButton = {
  controller: "keypad",
  key: 2,
  position: "2,0",
  title: "Office",
  plugin_uuid: "de.perdoctus.streamdeck.homeassistant",
  action_uuid: "de.perdoctus.streamdeck.homeassistant.entity",
  settings: {
    entityId: "light.office",
    mode: "toggle",
  },
  raw: {
    ActionID: "ha-light-action",
    LinkedTitle: false,
    Name: "Entity",
    Plugin: {
      Name: "Home Assistant",
      UUID: "de.perdoctus.streamdeck.homeassistant",
      Version: "3.7.1",
    },
    Settings: {
      entityId: "light.office",
      mode: "toggle",
    },
    State: 0,
    States: [
      {
        Title: "Office",
        Image: "Images/office.png",
      },
    ],
    UUID: "de.perdoctus.streamdeck.homeassistant.entity",
  },
};

export const PLUGIN_RECONFIG_CLAIM =
  "configured action reused; settings preserved";

export const buildReusedPluginButton = ({
  key,
  title,
}: {
  key: number;
  title: string;
}): PageButton => {
  const column = key % 9;
  const row = Math.floor(key / 9);

  return {
    ...sourcePluginButton,
    key,
    position: `${column},${row}`,
    title,
    settings: { ...sourcePluginButton.raw.Settings },
    raw: sourcePluginButton.raw,
  };
};

export type DeckButton = {
  title: string;
  glyph: string;
  color: string;
};

export const deckButtons: DeckButton[] = [
  { title: "#autojack", glyph: "A", color: "#2dd4bf" },
  { title: "#autostev", glyph: "W", color: "#f59e0b" },
  { title: "#reports", glyph: "R", color: "#34d399" },
  { title: "#ai-auto", glyph: "64", color: "#a78bfa" },
  { title: "#marketing", glyph: "M", color: "#fb7185" },
  { title: "#standup", glyph: "S", color: "#f8fafc" },
  { title: "#partners", glyph: "P", color: "#fbbf24" },
  { title: "#huddle", glyph: "H", color: "#fb7185" },
  { title: "Unread", glyph: "U", color: "#2dd4bf" },
  { title: "Home", glyph: "HA", color: "#22d3ee" },
  { title: "Wave", glyph: "WL", color: "#a78bfa" },
  { title: "Spotify", glyph: "SP", color: "#34d399" },
  { title: "GitHub", glyph: "GH", color: "#f8fafc" },
  { title: "Hue", glyph: "HU", color: "#fbbf24" },
  { title: "OBS", glyph: "OB", color: "#fb7185" },
  { title: "Store", glyph: "DB", color: "#fb7185" },
  { title: "Studio", glyph: "ST", color: "#22d3ee" },
  { title: "Deploy", glyph: "D", color: "#34d399" },
];

export type AudioCue = {
  src: string;
  from: number;
  volume: number;
};

export const audioCues: AudioCue[] = [
  { src: "audio/synth-bed.wav", from: 0, volume: 0.42 },
  { src: "audio/deep-hit.wav", from: 8, volume: 0.7 },
  { src: "audio/whoosh.wav", from: 196, volume: 0.55 },
  { src: "audio/ui-click.wav", from: 272, volume: 0.5 },
  { src: "audio/switch-hit.wav", from: 420, volume: 0.58 },
  { src: "audio/ui-click.wav", from: 525, volume: 0.45 },
  { src: "audio/whoosh.wav", from: 620, volume: 0.58 },
  { src: "audio/switch-hit.wav", from: 730, volume: 0.62 },
  { src: "audio/ui-click.wav", from: 888, volume: 0.45 },
  { src: "audio/deep-hit.wav", from: 1038, volume: 0.8 },
  { src: "audio/final-impact.wav", from: 1198, volume: 0.82 },
];
