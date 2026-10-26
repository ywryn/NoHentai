import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { validateTranslate } from './adminData.js'

export function translateConfig() {
  const config = validateTranslate(JSON.parse(readFileSync(join(process.cwd(), 'config/translate.json'), 'utf8')))
  return {
    model: config.model ?? process.env.LLM_MODEL ?? 'gpt-4o-mini',
    defaultOcr: config.defaultOcr,
    jsonMode: config.jsonMode ?? process.env.LLM_JSON_MODE === '1',
  }
}
