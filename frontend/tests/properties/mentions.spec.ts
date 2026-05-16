import { describe, expect, test } from 'vitest'
import fc from 'fast-check'
import type { MentionCandidate } from '@/types'
import { MENTION_PATTERN, parseMentionsRoundTrip } from '@/utils/mentions'

const KNOWN_CANDIDATES: MentionCandidate[] = [
  { author_id: 'u-alpha', github_login: 'alpha', display_name: 'Alpha' },
  { author_id: 'u-beta', github_login: 'beta', display_name: 'Beta' },
  { author_id: 'u-gamma', github_login: 'gamma', display_name: 'Gamma' },
  { author_id: 'u-dash', github_login: 'user-with-dash', display_name: 'Dash' },
]

function backendResolvedMentions(content: string): MentionCandidate[] {
  const byLogin = new Map(KNOWN_CANDIDATES.map((item) => [item.github_login.toLowerCase(), item]))
  const ordered: MentionCandidate[] = []
  const seen = new Set<string>()
  const pattern = new RegExp(MENTION_PATTERN)
  let match: RegExpExecArray | null = null

  while ((match = pattern.exec(content)) !== null) {
    const login = match[1].toLowerCase()
    if (seen.has(login)) {
      continue
    }
    seen.add(login)
    const candidate = byLogin.get(login)
    if (candidate) {
      ordered.push(candidate)
    }
  }

  return ordered
}

function backendFixtureSegments(content: string, resolvedMentions: MentionCandidate[]) {
  const lookup = new Map(resolvedMentions.map((item) => [item.github_login.toLowerCase(), item]))
  const segments: Array<{ type: 'text' | 'mention'; text: string; login?: string }> = []
  const pattern = new RegExp(MENTION_PATTERN)
  let cursor = 0
  let match: RegExpExecArray | null = null

  while ((match = pattern.exec(content)) !== null) {
    if (match.index > cursor) {
      segments.push({ type: 'text', text: content.slice(cursor, match.index) })
    }
    const token = match[0]
    const mention = lookup.get(match[1].toLowerCase())
    if (mention) {
      segments.push({ type: 'mention', text: token, login: mention.github_login })
    } else {
      segments.push({ type: 'text', text: token })
    }
    cursor = match.index + token.length
  }

  if (cursor < content.length) {
    segments.push({ type: 'text', text: content.slice(cursor) })
  }

  return segments.length ? segments : [{ type: 'text' as const, text: content }]
}

describe('parseMentionsRoundTrip property', () => {
  test('matches backend fixture semantics for generated content', () => {
    fc.assert(
      fc.property(
        fc.array(
          fc.constantFrom(
            'hello',
            'world',
            '@alpha',
            '@beta',
            '@gamma',
            '@user-with-dash',
            '@ghost-user',
            '@alpha,',
            '@beta.',
            '(note)',
            'plain-text',
          ),
          { maxLength: 20 },
        ),
        (chunks) => {
          const content = chunks.join(' ')
          const resolvedMentions = backendResolvedMentions(content)
          const actual = parseMentionsRoundTrip(content, resolvedMentions).map((segment) => ({
            type: segment.type,
            text: segment.text,
            login: segment.mention?.github_login,
          }))
          const expected = backendFixtureSegments(content, resolvedMentions)
          expect(actual).toEqual(expected)
        },
      ),
      { numRuns: 40 },
    )
  })
})