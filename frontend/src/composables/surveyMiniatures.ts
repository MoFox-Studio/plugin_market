// Four marked sites per map sheet. Five consecutive sheets contain the whole field guide.
export const miniatureNames = [
  'tent',
  'well',
  'wind-sock',
  'cairn',
  'cave',
  'falls',
  'aqueduct',
  'ferry',
  'signal-buoy',
  'cable-car',
  'trig-station',
  'sluice',
  'radio-mast',
  'waterwheel',
  'geyser',
  'rail-switch',
  'fossil',
  'rope-bridge',
  'snow-shelter',
  'tidal-gauge',
] as const;
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
      number: String(subject + 1).padStart(2, '0'),
      x: site.x + ((sheet * 41 + slot * 13 + offset) % 71) - 35,
      y: site.y + ((sheet * 17 + slot * 7 + offset) % 31) - 15,
    };
  });
}
