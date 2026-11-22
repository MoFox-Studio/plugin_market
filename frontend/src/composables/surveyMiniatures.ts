import { impressions } from './rareImpressions';
import reverie from '@/assets/impressions/reverie.svg?no-inline';

// The personal floral and portrait prints stay in the colophon, clear of the hero.
// Four marked sites per sheet reveal the twenty field plates over five sheets.
const fieldPrints = [
  ...impressions.filter((print) => print.id !== 'lycoris' && print.id !== 'tiger'),
  { id: 'airship', source: reverie + '#airship' },
  { id: 'paper-crane', source: reverie + '#paper-crane' },
];
export const miniatureNames = fieldPrints.map((print) => print.id);
const sites = [
  { x: 690, y: 117 },
  { x: 1440, y: 153 },
  { x: 515, y: 448 },
  { x: 1300, y: 513 },
];
const editionOffsets: Record<string, number> = {
  RIDGE: 0,
  ATLAS: 5,
  PROOF: 11,
  RELAY: 16,
};
export function surveyMiniatures(sheet: number, edition: string) {
  const offset = editionOffsets[edition] ?? 0;
  return sites.map((site, slot) => {
    const ordinal = sheet * sites.length + slot;
    const subject = (ordinal * 7 + offset) % miniatureNames.length;
    return {
      id: miniatureNames[subject],
      source: fieldPrints[subject].source,
      number: String(subject + 1).padStart(2, '0'),
      x: site.x + ((sheet * 41 + slot * 13 + offset) % 71) - 35,
      y: site.y + ((sheet * 17 + slot * 7 + offset) % 31) - 15,
    };
  });
}
