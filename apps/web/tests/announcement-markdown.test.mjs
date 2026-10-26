import assert from 'node:assert/strict'
import test from 'node:test'
import { renderAnnouncement } from '../app/utils/announcementMarkdown.ts'

test('announcement Markdown renders headings, lists and ordinary links', () => {
  const html = renderAnnouncement('## News\n\n- **New tool**\n\n[Tools](/tools)')
  assert.match(html, /<h2>News<\/h2>/)
  assert.match(html, /<strong>New tool<\/strong>/)
  assert.match(html, /href="\/tools" rel="noopener noreferrer"/)
})

test('raw HTML, embedded images and dangerous URL schemes are never executable', () => {
  for (const content of [
    '<script>alert(1)</script>', '<img src=x onerror=alert(1)>',
    '<svg onload=alert(1)>', '[click](javascript:alert(1))',
    '[click](JaVaScRiPt:alert%281%29)', '[click](data:text/html;base64,PHNjcmlwdD4=)',
    '![tracker](https://example.com/pixel.png)',
  ]) {
    const html = renderAnnouncement(content)
    assert.doesNotMatch(html, /<(script|img|svg|iframe)\b/i)
    assert.doesNotMatch(html, /href="(?:javascript|data|vbscript):/i)
  }
})
