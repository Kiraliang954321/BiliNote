import assert from 'node:assert/strict'
import test from 'node:test'

import { normalizeMathDelimiters } from './markdownmath.ts'

test('aligns display-math delimiters inside a markdown list item', () => {
  const input = String.raw`- **第三步：运用洛必达法则求导**
  对分子分母同时求导：
  \[
\text{原式} = \lim_{x \to 1} \frac{5x^4}{4x^3}
\]
- **第四步：约分与计算**`

  const expected = String.raw`- **第三步：运用洛必达法则求导**
  对分子分母同时求导：
  $$
  \text{原式} = \lim_{x \to 1} \frac{5x^4}{4x^3}
  $$
- **第四步：约分与计算**`

  assert.equal(normalizeMathDelimiters(input), expected)
})
