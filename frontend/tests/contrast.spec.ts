// @vitest-environment node
import { describe, expect, test } from 'vitest';
import { readFileSync } from 'node:fs';

const tokens = readFileSync('src/assets/tokens.css', 'utf8');

function luminance(hex: string) {
  const channels = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(value => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
const sections = tokens.split(':root[data-theme=\'dark\']');
describe('阅读文本对比度', () => {
  test.each(['light', 'dark'])('%s 主题的阅读文本与链接颜色在常用背景上满足 4.5:1 的对比度', theme => {
    const colors = Object.fromEntries([...sections[theme === 'light' ? 0 : 1].matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)]
      .map(match => [match[1], match[2]]));
    for (const ink of ['ink-900', 'ink-700', 'ink-500', 'ink-300', 'ink-200', 'blue-600', 'blue-700']) {
      for (const surface of ['paper', 'surface', 'surface-soft', 'surface-hover', 'surface-elevated']) {
        const foreground = luminance(colors[ink]);
        const background = luminance(colors[surface]);
        const ratio = (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
        expect(ratio, `${theme} 主题中 ${ink} 在 ${surface} 背景上的对比度`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
