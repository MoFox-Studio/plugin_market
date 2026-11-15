// @vitest-environment node
import { describe, expect, test } from 'vitest';
import { readFileSync } from 'node:fs';

const tokens = readFileSync('src/assets/tokens.css', 'utf8');

function luminance(hex: string) {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
const sections = tokens.split(":root[data-theme='dark']");
describe('reading text contrast', () => {
  test.each(['light', 'dark'])('%s reading and link colors meet 4.5:1 on common surfaces', theme => {
    const colors = Object.fromEntries([...sections[theme === 'light' ? 0 : 1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)]
      .map(match => [match[1], match[2]]));
    for (const ink of ['ink-900', 'ink-700', 'ink-500', 'ink-300', 'ink-200', 'blue-600', 'blue-700']) {
      for (const surface of ['paper', 'surface', 'surface-soft', 'surface-hover', 'surface-elevated']) {
        const foreground = luminance(colors[ink]);
        const background = luminance(colors[surface]);
        const ratio = (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
        expect(ratio, `${theme} ${ink} on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
