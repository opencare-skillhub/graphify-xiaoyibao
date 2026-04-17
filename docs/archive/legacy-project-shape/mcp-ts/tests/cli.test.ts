import test from 'node:test'
import assert from 'node:assert/strict'

import { buildCommand } from '../src/cli.ts'

test('xyb cli registers scan/report/serve commands', () => {
  const program = buildCommand()
  const names = program.commands.map((cmd) => cmd.name())
  assert.ok(names.includes('scan'))
  assert.ok(names.includes('report'))
  assert.ok(names.includes('serve'))
})
