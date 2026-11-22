/** Interpret a deep link before the route scroll coordinator looks for its target. */
export function dossierChapter(
  hash: string,
): 'overview' | 'readme' | 'versions' | 'comments' {
  let anchor = hash.replace(/^#/, '');
  try {
    anchor = decodeURIComponent(anchor);
  } catch {
    /* Keep malformed IDs literal. */
  }
  if (!anchor || ['overview', 'dependencies', 'maintainers'].includes(anchor))
    return 'overview';
  if (anchor === 'comments' || anchor.startsWith('comment-')) return 'comments';
  if (anchor === 'versions' || anchor.startsWith('version-')) return 'versions';
  // Markdown headings are author-defined. Any other fragment opens the document.
  return 'readme';
}
