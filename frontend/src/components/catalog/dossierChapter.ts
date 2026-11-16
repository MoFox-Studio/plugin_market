/** 在路由滚动协调器查找目标之前解析深层链接。 */
export function dossierChapter(
  hash: string,
): 'overview' | 'readme' | 'versions' | 'comments' {
  let anchor = hash.replace(/^#/, '');
  try {
    anchor = decodeURIComponent(anchor);
  } catch {
    // 保留格式错误的 ID 原文。
  }
  if (!anchor || ['overview', 'dependencies', 'maintainers'].includes(anchor))
    return 'overview';
  if (anchor === 'comments' || anchor.startsWith('comment-')) return 'comments';
  if (anchor === 'versions' || anchor.startsWith('version-')) return 'versions';
  // Markdown 标题由作者定义，其他片段标识均打开文档。
  return 'readme';
}
