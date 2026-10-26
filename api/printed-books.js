import { handleTransOptions, setTransCors } from './_trans-cors.js'

// Retire the former translation-password write path. All editing lives in Admin.
export default async function handler(req, res) {
  if (handleTransOptions(req, res)) return
  setTransCors(req, res)
  res.setHeader('Cache-Control', 'no-store')
  return res.status(410).json({ error: '书单编辑已迁移到 /#/admin/printed，请使用独立管理密码' })
}
