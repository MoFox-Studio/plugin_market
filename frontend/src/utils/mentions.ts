import type { MentionCandidate } from '@/types'

export interface MentionSegment {
  type: 'text' | 'mention'
  text: string
  mention?: MentionCandidate
}

export const MENTION_PATTERN = /@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))(?![A-Za-z0-9-])/g

export function parseMentionsRoundTrip(
  content: string,
  resolvedMentions: MentionCandidate[] = [],
): MentionSegment[] {
  const matches = new Map(
    resolvedMentions.map((mention) => [mention.github_login.toLowerCase(), mention]),
  )
  const segments: MentionSegment[] = []
  const pattern = new RegExp(MENTION_PATTERN)
  let cursor = 0
  let match: RegExpExecArray | null = null

  while ((match = pattern.exec(content)) !== null) {
    if (match.index > cursor) {
      segments.push({ type: 'text', text: content.slice(cursor, match.index) })
    }

    const token = match[0]
    const mention = matches.get(match[1].toLowerCase())
    if (mention) {
      segments.push({ type: 'mention', text: token, mention })
    } else {
      segments.push({ type: 'text', text: token })
    }
    cursor = match.index + token.length
  }

  if (cursor < content.length) {
    segments.push({ type: 'text', text: content.slice(cursor) })
  }

  return segments.length ? segments : [{ type: 'text', text: content }]
}