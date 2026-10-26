import MarkdownIt from 'markdown-it'

// Raw HTML and embedded images stay disabled for both preview and public content.
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false }).disable('image')
const defaultLink = markdown.renderer.rules.link_open
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index]?.attrSet('rel', 'noopener noreferrer')
  return defaultLink ? defaultLink(tokens, index, options, env, self) : self.renderToken(tokens, index, options)
}

export function renderAnnouncement(content: string) {
  return markdown.render(content)
}
