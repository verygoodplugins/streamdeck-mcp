import { describe, expect, it } from "vitest";
import {
  audioCues,
  buildReusedPluginButton,
  PLUGIN_RECONFIG_CLAIM,
  scenes,
  sourcePluginButton,
  trailerConfig,
} from "./trailerData";

describe("trailer data", () => {
  it("defines the requested 45-second 16:9 Remotion composition", () => {
    expect(trailerConfig.id).toBe("StreamDeckTrailer");
    expect(trailerConfig.width).toBe(1920);
    expect(trailerConfig.height).toBe(1080);
    expect(trailerConfig.fps).toBe(30);
    expect(trailerConfig.durationInFrames).toBe(1350);
  });

  it("covers every planned product beat in timeline order", () => {
    expect(scenes.map((scene) => scene.id)).toEqual([
      "hook",
      "inventory",
      "plugin-scan",
      "raw-action-reuse",
      "icon-script-write",
      "final-reveal",
    ]);

    scenes.slice(1).forEach((scene, index) => {
      const previous = scenes[index];
      expect(scene.from).toBeGreaterThanOrEqual(previous.from + previous.duration);
    });
  });

  it("keeps the plugin reconfiguration claim precise", () => {
    expect(PLUGIN_RECONFIG_CLAIM).toContain("configured action reused");
    expect(PLUGIN_RECONFIG_CLAIM).toContain("settings preserved");
    expect(PLUGIN_RECONFIG_CLAIM.toLowerCase()).not.toContain("infer");
  });

  it("reuses raw plugin action settings while changing placement and title", () => {
    const reused = buildReusedPluginButton({
      key: 17,
      title: "Studio Lights",
    });

    expect(reused.raw).toEqual(sourcePluginButton.raw);
    expect(reused.settings).toEqual({
      entityId: "light.office",
      mode: "toggle",
    });
    expect(reused.title).toBe("Studio Lights");
    expect(reused.key).toBe(17);
  });

  it("uses only local audio assets and cues them inside the composition", () => {
    expect(audioCues.length).toBeGreaterThan(4);
    audioCues.forEach((cue) => {
      expect(cue.src).toMatch(/^audio\//);
      expect(cue.from).toBeGreaterThanOrEqual(0);
      expect(cue.from).toBeLessThan(trailerConfig.durationInFrames);
    });
  });
});
