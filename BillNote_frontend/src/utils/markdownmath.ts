/**
 * Converts TeX-style delimiters to the dollar delimiters recognized by remark-math.
 * Code fences and inline code spans are copied verbatim.
 */
export function normalizeMathDelimiters(markdown: string): string {
  const normalizeText = (text: string) =>
    text
      .replace(/\\\[([\s\S]*?)\\\]/g, (_match, math: string) => `$$${math}$$`)
      .replace(/\\\(([\s\S]*?)\\\)/g, (_match, math: string) => `$${math}$`)

  let result = ''
  let textBuffer = ''
  let index = 0

  const flushText = () => {
    result += normalizeText(textBuffer)
    textBuffer = ''
  }

  while (index < markdown.length) {
    const atLineStart = index === 0 || markdown[index - 1] === '\n'
    if (atLineStart) {
      const lineEnd = markdown.indexOf('\n', index)
      const openingLine = markdown.slice(index, lineEnd === -1 ? markdown.length : lineEnd)
      const openingFence = openingLine.match(/^ {0,3}(`{3,}|~{3,})/)

      if (openingFence) {
        const fence = openingFence[1]
        const fenceCharacter = fence[0]
        const closingFence = new RegExp(`^ {0,3}${fenceCharacter}{${fence.length},}[ \\t]*$`)
        let fenceEnd = lineEnd === -1 ? markdown.length : lineEnd + 1
        let closingFound = false

        while (fenceEnd < markdown.length) {
          const closingLineEnd = markdown.indexOf('\n', fenceEnd)
          const closingLine = markdown.slice(
            fenceEnd,
            closingLineEnd === -1 ? markdown.length : closingLineEnd,
          )
          if (closingFence.test(closingLine)) {
            fenceEnd = closingLineEnd === -1 ? markdown.length : closingLineEnd + 1
            closingFound = true
            break
          }
          fenceEnd = closingLineEnd === -1 ? markdown.length : closingLineEnd + 1
        }

        flushText()
        result += markdown.slice(index, closingFound ? fenceEnd : markdown.length)
        index = closingFound ? fenceEnd : markdown.length
        continue
      }
    }

    if (markdown[index] === '`') {
      let tickCount = 1
      while (markdown[index + tickCount] === '`') tickCount += 1
      const delimiter = '`'.repeat(tickCount)
      let closingIndex = markdown.indexOf(delimiter, index + tickCount)

      while (
        closingIndex !== -1 &&
        (markdown[closingIndex - 1] === '`' || markdown[closingIndex + tickCount] === '`')
      ) {
        closingIndex = markdown.indexOf(delimiter, closingIndex + tickCount)
      }

      if (closingIndex !== -1) {
        flushText()
        result += markdown.slice(index, closingIndex + tickCount)
        index = closingIndex + tickCount
        continue
      }
    }

    textBuffer += markdown[index]
    index += 1
  }

  flushText()
  return result
}
