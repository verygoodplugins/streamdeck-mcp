import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  PLUGIN_RECONFIG_CLAIM,
  audioCues,
  buildReusedPluginButton,
  deckButtons,
  installedPlugins,
  scenes,
  sourcePluginButton,
} from "./trailerData";

const colors = {
  background: "#05070d",
  panel: "#101624",
  panelStrong: "#151d2e",
  border: "rgba(148, 163, 184, 0.22)",
  text: "#f8fafc",
  muted: "#94a3b8",
  teal: "#2dd4bf",
  cyan: "#22d3ee",
  amber: "#fbbf24",
  rose: "#fb7185",
  violet: "#a78bfa",
  green: "#34d399",
};

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const clamp = {
  extrapolateLeft: "clamp" as const,
  extrapolateRight: "clamp" as const,
};

const enter = (frame: number, start = 0, end = 24) =>
  interpolate(frame, [start, end], [0, 1], { ...clamp, easing: ease });

const drift = (frame: number, amount = 1) =>
  Math.sin(frame / 45) * amount + Math.cos(frame / 73) * amount * 0.55;

const seconds = (value: number, fps: number) => Math.round(value * fps);

const sceneById = Object.fromEntries(scenes.map((scene) => [scene.id, scene]));

type TextBlockProps = {
  eyebrow: string;
  headline: string;
  body?: string;
  align?: "left" | "center";
};

const TextBlock: React.FC<TextBlockProps> = ({
  eyebrow,
  headline,
  body,
  align = "left",
}) => {
  const frame = useCurrentFrame();
  const opacity = enter(frame, 2, 28);
  const y = interpolate(opacity, [0, 1], [28, 0]);

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${y}px)`,
        textAlign: align,
        maxWidth: align === "center" ? 1120 : 780,
      }}
    >
      <div
        style={{
          color: colors.teal,
          fontSize: 28,
          fontWeight: 800,
          letterSpacing: 0,
          marginBottom: 18,
          textTransform: "uppercase",
        }}
      >
        {eyebrow}
      </div>
      <div
        style={{
          color: colors.text,
          fontSize: align === "center" ? 84 : 74,
          fontWeight: 900,
          letterSpacing: 0,
          lineHeight: 0.96,
        }}
      >
        {headline}
      </div>
      {body ? (
        <div
          style={{
            color: colors.muted,
            fontSize: 30,
            lineHeight: 1.32,
            marginTop: 28,
            maxWidth: 760,
          }}
        >
          {body}
        </div>
      ) : null}
    </div>
  );
};

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const glow = interpolate(Math.sin(frame / 58), [-1, 1], [0.35, 0.85]);

  return (
    <AbsoluteFill
      style={{
        background: colors.background,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 25% 20%, rgba(45,212,191,0.16), transparent 30%), radial-gradient(circle at 75% 12%, rgba(251,113,133,0.13), transparent 28%), radial-gradient(circle at 72% 80%, rgba(167,139,250,0.13), transparent 32%)",
          opacity: glow,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.05) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "linear-gradient(to bottom, transparent, black 14%, black 86%, transparent)",
          opacity: 0.4,
          transform: `translateY(${(frame % 64) * -0.35}px)`,
        }}
      />
    </AbsoluteFill>
  );
};

type GlassPanelProps = {
  children: React.ReactNode;
  style?: React.CSSProperties;
};

const GlassPanel: React.FC<GlassPanelProps> = ({ children, style }) => (
  <div
    style={{
      background:
        "linear-gradient(145deg, rgba(21,29,46,0.96), rgba(8,13,24,0.92))",
      border: `1px solid ${colors.border}`,
      borderRadius: 24,
      boxShadow: "0 34px 120px rgba(0,0,0,0.45)",
      ...style,
    }}
  >
    {children}
  </div>
);

const BrowserShell: React.FC<{
  title: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ title, children, style }) => (
  <GlassPanel style={{ overflow: "hidden", ...style }}>
    <div
      style={{
        height: 58,
        borderBottom: `1px solid ${colors.border}`,
        display: "flex",
        alignItems: "center",
        padding: "0 24px",
        gap: 12,
      }}
    >
      {["#fb7185", "#fbbf24", "#34d399"].map((color) => (
        <div
          key={color}
          style={{ width: 14, height: 14, borderRadius: 999, background: color }}
        />
      ))}
      <div
        style={{
          color: colors.muted,
          fontSize: 18,
          marginLeft: 16,
          fontWeight: 700,
        }}
      >
        {title}
      </div>
    </div>
    {children}
  </GlassPanel>
);

const ToolPill: React.FC<{ label: string; active?: boolean; delay?: number }> = ({
  label,
  active = false,
  delay = 0,
}) => {
  const frame = useCurrentFrame();
  const opacity = enter(frame, delay, delay + 18);
  return (
    <div
      style={{
        opacity,
        transform: `translateY(${interpolate(opacity, [0, 1], [18, 0])}px)`,
        color: active ? colors.background : colors.text,
        background: active ? colors.teal : "rgba(15,23,42,0.84)",
        border: `1px solid ${active ? "rgba(45,212,191,0.8)" : colors.border}`,
        borderRadius: 999,
        padding: "12px 18px",
        fontSize: 20,
        fontWeight: 800,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </div>
  );
};

const MiniDeck: React.FC<{ emphasize?: number; compact?: boolean }> = ({
  emphasize,
  compact = false,
}) => {
  const frame = useCurrentFrame();
  const columns = compact ? 6 : 9;
  const buttons = compact ? deckButtons.slice(0, 18) : deckButtons;

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${columns}, ${compact ? 74 : 82}px)`,
        gap: compact ? 12 : 14,
      }}
    >
      {buttons.map((button, index) => {
        const opacity = enter(frame, index * 2, index * 2 + 18);
        const active = index === emphasize;
        return (
          <div
            key={`${button.title}-${index}`}
            style={{
              width: compact ? 74 : 82,
              height: compact ? 74 : 82,
              borderRadius: 16,
              border: `1px solid ${active ? button.color : "rgba(148,163,184,0.26)"}`,
              background: active
                ? `linear-gradient(160deg, ${button.color}, rgba(15,23,42,0.95) 64%)`
                : "linear-gradient(160deg, #111827, #05070d)",
              boxShadow: active
                ? `0 0 34px ${button.color}88`
                : "inset 0 0 0 1px rgba(255,255,255,0.04)",
              opacity,
              transform: `translateY(${interpolate(opacity, [0, 1], [18, 0])}px) scale(${
                active ? 1.06 : 1
              })`,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 6,
            }}
          >
            <div
              style={{
                color: active ? colors.text : button.color,
                fontWeight: 950,
                fontSize: compact ? 21 : 24,
                letterSpacing: 0,
              }}
            >
              {button.glyph}
            </div>
            <div
              style={{
                color: colors.text,
                fontSize: compact ? 11 : 12,
                fontWeight: 800,
                maxWidth: compact ? 62 : 72,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {button.title}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const HookScene: React.FC = () => {
  const frame = useCurrentFrame();
  const deckOpacity = enter(frame, 36, 76);
  const rotate = interpolate(deckOpacity, [0, 1], [-8, -2]);

  return (
    <AbsoluteFill style={{ padding: 96 }}>
      <div style={{ display: "flex", alignItems: "center", height: "100%" }}>
        <div style={{ width: "52%" }}>
          <TextBlock
            eyebrow={sceneById.hook.eyebrow}
            headline={sceneById.hook.headline}
            body="Profiles, icons, dials, scripts, and existing plugin actions. Authored from one prompt."
          />
          <div style={{ display: "flex", gap: 14, marginTop: 42, flexWrap: "wrap" }}>
            <ToolPill label="read profiles" active delay={28} />
            <ToolPill label="read plugins" delay={40} />
            <ToolPill label="write page" delay={52} />
          </div>
        </div>
        <div
          style={{
            width: "48%",
            height: 680,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            perspective: 1200,
          }}
        >
          <div
            style={{
              opacity: deckOpacity,
              transform: `rotateX(8deg) rotateZ(${rotate}deg) translateY(${drift(
                frame,
                8,
              )}px)`,
            }}
          >
            <BrowserShell title="Prompt -> Stream Deck profile" style={{ width: 780 }}>
              <div style={{ padding: 34 }}>
                <div
                  style={{
                    color: colors.text,
                    fontSize: 26,
                    lineHeight: 1.35,
                    fontWeight: 800,
                    marginBottom: 26,
                  }}
                >
                  "Make me a Slack control board using my real plugins."
                </div>
                <MiniDeck compact />
              </div>
            </BrowserShell>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const InventoryScene: React.FC = () => {
  const frame = useCurrentFrame();
  const meter = enter(frame, 16, 54);

  return (
    <AbsoluteFill style={{ padding: 92 }}>
      <div style={{ display: "grid", gridTemplateColumns: "0.9fr 1.1fr", gap: 58 }}>
        <TextBlock
          eyebrow={sceneById["inventory"].eyebrow}
          headline={sceneById["inventory"].headline}
          body="The agent reads profile manifests first, then matches layout choices to the actual device model."
        />
        <BrowserShell title="streamdeck_read_profiles" style={{ height: 820 }}>
          <div style={{ padding: 34 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              {[
                ["ModelName", "Stream Deck + XL", colors.teal],
                ["Key grid", "9 x 4", colors.cyan],
                ["Dials", "6 encoders", colors.violet],
                ["Touch strip", "1200 x 100", colors.amber],
              ].map(([label, value, color], index) => {
                const opacity = enter(frame, 12 + index * 8, 34 + index * 8);
                return (
                  <GlassPanel
                    key={label}
                    style={{
                      padding: 24,
                      opacity,
                      transform: `translateY(${interpolate(opacity, [0, 1], [24, 0])}px)`,
                    }}
                  >
                    <div style={{ color: colors.muted, fontSize: 18, fontWeight: 800 }}>
                      {label}
                    </div>
                    <div
                      style={{
                        color: color as string,
                        fontSize: 34,
                        fontWeight: 950,
                        marginTop: 8,
                      }}
                    >
                      {value}
                    </div>
                  </GlassPanel>
                );
              })}
            </div>
            <div style={{ marginTop: 36 }}>
              <MiniDeck emphasize={Math.floor(interpolate(meter, [0, 1], [0, 17]))} />
            </div>
            <div
              style={{
                height: 86,
                marginTop: 26,
                borderRadius: 18,
                border: `1px solid ${colors.border}`,
                background:
                  "linear-gradient(90deg, rgba(45,212,191,0.18), rgba(34,211,238,0.12), rgba(251,113,133,0.18))",
                display: "grid",
                gridTemplateColumns: "repeat(6, 1fr)",
                alignItems: "center",
                padding: "0 28px",
                gap: 16,
              }}
            >
              {Array.from({ length: 6 }).map((_, index) => (
                <div
                  key={index}
                  style={{
                    height: 42,
                    borderRadius: 999,
                    border: `2px solid ${index < meter * 6 ? colors.teal : colors.border}`,
                    boxShadow:
                      index < meter * 6 ? `0 0 28px ${colors.teal}77` : "none",
                  }}
                />
              ))}
            </div>
          </div>
        </BrowserShell>
      </div>
    </AbsoluteFill>
  );
};

const PluginScanScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ padding: 92 }}>
      <div style={{ display: "grid", gridTemplateColumns: "0.82fr 1.18fr", gap: 58 }}>
        <TextBlock
          eyebrow={sceneById["plugin-scan"].eyebrow}
          headline={sceneById["plugin-scan"].headline}
          body="Readable plugin manifests become a catalog of action UUIDs and controller support."
        />
        <BrowserShell title="Installed plugin catalog" style={{ height: 820 }}>
          <div style={{ padding: 30 }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1.1fr 1.7fr 0.9fr 1.1fr",
                color: colors.muted,
                fontSize: 16,
                fontWeight: 900,
                borderBottom: `1px solid ${colors.border}`,
                padding: "0 12px 14px",
                textTransform: "uppercase",
              }}
            >
              <span>Plugin</span>
              <span>UUID</span>
              <span>Actions</span>
              <span>Controllers</span>
            </div>
            {installedPlugins.map((plugin, index) => {
              const opacity = enter(frame, 18 + index * 11, 40 + index * 11);
              return (
                <div
                  key={plugin.uuid}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1.1fr 1.7fr 0.9fr 1.1fr",
                    alignItems: "center",
                    minHeight: 96,
                    padding: "0 12px",
                    borderBottom: `1px solid rgba(148,163,184,0.14)`,
                    opacity,
                    transform: `translateX(${interpolate(opacity, [0, 1], [40, 0])}px)`,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                    <div
                      style={{
                        width: 42,
                        height: 42,
                        borderRadius: 12,
                        background: `${plugin.color}24`,
                        border: `1px solid ${plugin.color}`,
                        color: plugin.color,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 950,
                      }}
                    >
                      {plugin.name.slice(0, 2)}
                    </div>
                    <div style={{ color: colors.text, fontSize: 24, fontWeight: 900 }}>
                      {plugin.name}
                    </div>
                  </div>
                  <code style={{ color: colors.muted, fontSize: 16 }}>{plugin.uuid}</code>
                  <div style={{ color: colors.amber, fontSize: 25, fontWeight: 950 }}>
                    {plugin.actionCount}
                  </div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {plugin.controllers.map((controller) => (
                      <span
                        key={controller}
                        style={{
                          color: colors.text,
                          background: "rgba(15,23,42,0.9)",
                          border: `1px solid ${colors.border}`,
                          borderRadius: 999,
                          padding: "7px 10px",
                          fontSize: 14,
                          fontWeight: 800,
                        }}
                      >
                        {controller}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
            <div
              style={{
                marginTop: 26,
                color: colors.green,
                fontSize: 22,
                fontWeight: 900,
              }}
            >
              Protected or binary manifests report diagnostics instead of stopping the scan.
            </div>
          </div>
        </BrowserShell>
      </div>
    </AbsoluteFill>
  );
};

const RawJson: React.FC<{ title: string; lines: string[]; activeLine?: number }> = ({
  title,
  lines,
  activeLine,
}) => {
  const frame = useCurrentFrame();

  return (
    <GlassPanel style={{ padding: 22, minHeight: 420 }}>
      <div
        style={{
          color: colors.text,
          fontSize: 23,
          fontWeight: 950,
          marginBottom: 18,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontFamily: "Menlo, Monaco, Consolas, monospace",
          fontSize: 17,
          lineHeight: 1.55,
          color: colors.muted,
        }}
      >
        {lines.map((line, index) => {
          const active = index === activeLine;
          const opacity = enter(frame, index * 4, index * 4 + 12);
          return (
            <div
              key={`${line}-${index}`}
              style={{
                opacity,
                color: active ? colors.teal : colors.muted,
                background: active ? "rgba(45,212,191,0.1)" : "transparent",
                borderRadius: 8,
                padding: "0 8px",
                whiteSpace: "pre",
              }}
            >
              {line}
            </div>
          );
        })}
      </div>
    </GlassPanel>
  );
};

const RawActionReuseScene: React.FC = () => {
  const frame = useCurrentFrame();
  const reused = buildReusedPluginButton({ key: 17, title: "Studio Lights" });
  const scanProgress = enter(frame, 0, 80);
  const claimOpacity = enter(frame, 112, 142);

  return (
    <AbsoluteFill style={{ padding: 72 }}>
      <TextBlock
        eyebrow={sceneById["raw-action-reuse"].eyebrow}
        headline={sceneById["raw-action-reuse"].headline}
        body="No private settings schema is guessed. Configured raw action data is copied, then the visible button metadata changes."
      />
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: 24,
          marginTop: 48,
        }}
      >
        <RawJson
          title="1. discover action"
          activeLine={4}
          lines={[
            "{",
            '  "plugin": "Home Assistant",',
            '  "action": "Entity",',
            '  "controllers": ["Keypad", "Encoder"],',
            '  "uuid": "de.perdoctus...entity"',
            "}",
          ]}
        />
        <RawJson
          title="2. read configured button.raw"
          activeLine={4}
          lines={[
            "{",
            '  "Name": "Entity",',
            '  "Plugin": {"Name": "Home Assistant"},',
            '  "Settings": {',
            `    "entityId": "${sourcePluginButton.settings.entityId}",`,
            `    "mode": "${sourcePluginButton.settings.mode}"`,
            "  }",
            "}",
          ]}
        />
        <RawJson
          title="3. write reused action"
          activeLine={5}
          lines={[
            "{",
            `  "key": ${reused.key},`,
            `  "title": "${reused.title}",`,
            '  "action": button.raw,',
            '  "settings": {',
            `    "entityId": "${reused.settings.entityId}"`,
            "  }",
            "}",
          ]}
        />
      </div>
      <div
        style={{
          position: "absolute",
          right: 92,
          bottom: 74,
          display: "flex",
          alignItems: "center",
          gap: 18,
          opacity: claimOpacity,
          transform: `translateY(${interpolate(claimOpacity, [0, 1], [24, 0])}px)`,
        }}
      >
        {PLUGIN_RECONFIG_CLAIM.split("; ").map((claim) => (
          <div
            key={claim}
            style={{
              color: colors.background,
              background: colors.green,
              borderRadius: 999,
              padding: "14px 20px",
              fontSize: 23,
              fontWeight: 950,
              boxShadow: `0 0 38px ${colors.green}55`,
            }}
          >
            {claim}
          </div>
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          left: 92,
          bottom: 86,
          width: 520,
          height: 12,
          borderRadius: 999,
          background: "rgba(148,163,184,0.18)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${scanProgress * 100}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${colors.cyan}, ${colors.teal}, ${colors.green})`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};

const IconScriptWriteScene: React.FC = () => {
  const frame = useCurrentFrame();
  const steps = [
    ["streamdeck_create_icon", "~7,400 bundled MDI glyphs"],
    ["streamdeck_create_action", "standalone shell scripts"],
    ["streamdeck_write_page", "atomic manifest rewrite"],
    ["streamdeck_restart_app", "device reloads the profile"],
  ];

  return (
    <AbsoluteFill style={{ padding: 92 }}>
      <div style={{ display: "grid", gridTemplateColumns: "0.92fr 1.08fr", gap: 62 }}>
        <TextBlock
          eyebrow={sceneById["icon-script-write"].eyebrow}
          headline={sceneById["icon-script-write"].headline}
          body="The desktop app gets a finished profile. The buttons run locally after the agent is gone."
        />
        <div style={{ display: "grid", gap: 20 }}>
          {steps.map(([name, detail], index) => {
            const opacity = enter(frame, 16 + index * 22, 40 + index * 22);
            return (
              <GlassPanel
                key={name}
                style={{
                  minHeight: 132,
                  padding: "26px 30px",
                  display: "flex",
                  alignItems: "center",
                  gap: 24,
                  opacity,
                  transform: `translateX(${interpolate(opacity, [0, 1], [44, 0])}px)`,
                }}
              >
                <div
                  style={{
                    width: 58,
                    height: 58,
                    borderRadius: 18,
                    background: index % 2 ? colors.violet : colors.teal,
                    color: colors.background,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 26,
                    fontWeight: 950,
                  }}
                >
                  {index + 1}
                </div>
                <div>
                  <div style={{ color: colors.text, fontSize: 31, fontWeight: 950 }}>
                    {name}
                  </div>
                  <div style={{ color: colors.muted, fontSize: 22, marginTop: 6 }}>
                    {detail}
                  </div>
                </div>
              </GlassPanel>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const FinalRevealScene: React.FC = () => {
  const frame = useCurrentFrame();
  const imageOpacity = enter(frame, 0, 42);
  const scale = interpolate(frame, [0, 300], [1.06, 1], clamp);
  const badgeOpacity = enter(frame, 88, 124);
  const titleOpacity = enter(frame, 18, 54);

  return (
    <AbsoluteFill style={{ padding: 64 }}>
      <div
        style={{
          position: "absolute",
          top: 56,
          left: 86,
          right: 86,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          zIndex: 4,
        }}
      >
        <div
          style={{
            opacity: titleOpacity,
            transform: `translateY(${interpolate(titleOpacity, [0, 1], [24, 0])}px)`,
            maxWidth: 920,
          }}
        >
          <div
            style={{
              color: colors.teal,
              fontSize: 24,
              fontWeight: 900,
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            {sceneById["final-reveal"].eyebrow}
          </div>
          <div
            style={{
              color: colors.text,
              fontSize: 54,
              fontWeight: 950,
              lineHeight: 1.02,
              letterSpacing: 0,
            }}
          >
            {sceneById["final-reveal"].headline}
          </div>
        </div>
        <div
          style={{
            opacity: badgeOpacity,
            color: colors.background,
            background: colors.teal,
            borderRadius: 999,
            padding: "18px 26px",
            fontSize: 25,
            fontWeight: 950,
          }}
        >
          uvx streamdeck-mcp
        </div>
      </div>
      <GlassPanel
        style={{
          position: "absolute",
          left: 176,
          right: 176,
          top: 250,
          height: 650,
          overflow: "hidden",
          opacity: imageOpacity,
          transform: `scale(${scale}) translateY(${drift(frame, 4)}px)`,
          transformOrigin: "center center",
        }}
      >
        <Img
          src={staticFile("images/slack-control-board.jpg")}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: "center 34%",
            filter: "saturate(1.08) contrast(1.04)",
          }}
        />
      </GlassPanel>
      <div
        style={{
          position: "absolute",
          bottom: 42,
          left: 0,
          right: 0,
          display: "flex",
          justifyContent: "center",
          gap: 16,
          opacity: badgeOpacity,
        }}
      >
        {["ProfilesV3", "offline MDI icons", "shell scripts", "plugin actions"].map(
          (label) => (
            <div
              key={label}
              style={{
                color: colors.text,
                background: "rgba(15,23,42,0.86)",
                border: `1px solid ${colors.border}`,
                borderRadius: 999,
                padding: "13px 18px",
                fontSize: 20,
                fontWeight: 850,
              }}
            >
              {label}
            </div>
          ),
        )}
      </div>
    </AbsoluteFill>
  );
};

const SceneSequence: React.FC<{
  from: number;
  duration: number;
  children: React.ReactNode;
}> = ({ from, duration, children }) => (
  <Sequence from={from} durationInFrames={duration} premountFor={30}>
    {children}
  </Sequence>
);

const TrailerAudio: React.FC = () => {
  const { fps } = useVideoConfig();

  return (
    <>
      {audioCues.map((cue, index) => (
        <Sequence
          key={`${cue.src}-${cue.from}-${index}`}
          from={cue.from}
          premountFor={seconds(0.25, fps)}
        >
          <Audio
            src={staticFile(cue.src)}
            volume={(audioFrame) => {
              if (cue.src !== "audio/synth-bed.wav") {
                return cue.volume;
              }

              return (
                cue.volume *
                interpolate(
                  audioFrame,
                  [0, seconds(2, fps), seconds(42, fps), seconds(45, fps)],
                  [0, 1, 1, 0],
                  clamp,
                )
              );
            }}
          />
        </Sequence>
      ))}
    </>
  );
};

export const StreamDeckTrailer: React.FC = () => {
  return (
    <AbsoluteFill style={{ background: colors.background }}>
      <Background />
      <SceneSequence from={sceneById.hook.from} duration={sceneById.hook.duration}>
        <HookScene />
      </SceneSequence>
      <SceneSequence
        from={sceneById.inventory.from}
        duration={sceneById.inventory.duration}
      >
        <InventoryScene />
      </SceneSequence>
      <SceneSequence
        from={sceneById["plugin-scan"].from}
        duration={sceneById["plugin-scan"].duration}
      >
        <PluginScanScene />
      </SceneSequence>
      <SceneSequence
        from={sceneById["raw-action-reuse"].from}
        duration={sceneById["raw-action-reuse"].duration}
      >
        <RawActionReuseScene />
      </SceneSequence>
      <SceneSequence
        from={sceneById["icon-script-write"].from}
        duration={sceneById["icon-script-write"].duration}
      >
        <IconScriptWriteScene />
      </SceneSequence>
      <SceneSequence
        from={sceneById["final-reveal"].from}
        duration={sceneById["final-reveal"].duration}
      >
        <FinalRevealScene />
      </SceneSequence>
      <TrailerAudio />
    </AbsoluteFill>
  );
};
