import lycoris from '@/assets/lycoris-radiata.svg?no-inline';
import tiger from '@/assets/tiger-rosette.webp?no-inline';
import seals from '@/assets/rare-impressions.svg?no-inline';

export const impressions = [
  {
    name: '彼岸花',
    caption: 'Lycoris radiata',
    collection: '植物图录',
    ink: 'var(--botanical-ink)',
    source: lycoris + '#lycoris-radiata',
    mask: false,
    alt: '彼岸花线刻，右下角题署 design by Lycoris radiata',
  },
  {
    name: '花饰虎耳',
    caption: 'The Rosette',
    collection: '人物图录',
    ink: 'var(--ink-900)',
    source: tiger,
    mask: true,
    alt: '虎耳少女线稿，发间别着花饰，双手举在胸前，条纹尾巴卷在身旁',
  },
  {
    name: '夜航信使',
    caption: 'Night Post',
    collection: '飞羽图录',
    ink: 'var(--blue-700)',
    source: seals + '#night-post',
    mask: false,
    alt: '月光下，一只燕子衔着信封掠过天空',
  },
  {
    name: '袖珍星图',
    caption: 'A Pocket Sky',
    collection: '天文图录',
    ink: 'var(--blue-900)',
    source: seals + '#pocket-sky',
    mask: false,
    alt: '黄铜怀表盘里嵌着一幅星图',
  },
] as const;
export type Impression = (typeof impressions)[number];

export function drawImpression(random = Math.random): Impression | null {
  if (random() >= 0.01) return null;
  return impressions[Math.floor(random() * impressions.length)];
}
