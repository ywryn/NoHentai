<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const urlInput = ref('')
const parseError = ref('')
const urlInputRef = ref(null)

onMounted(() => {
  setTimeout(() => urlInputRef.value?.focus(), 50)
})

// 解析 e-hentai/exhentai URL，提取 gid 和 token
const URL_RE = /https?:\/\/(?:e-hentai|exhentai)\.org\/g\/(\d+)\/([a-f0-9]+)/i

function handleGo() {
  parseError.value = ''
  const raw = urlInput.value.trim()
  if (!raw) {
    parseError.value = '请输入 URL'
    return
  }
  const m = raw.match(URL_RE)
  if (!m) {
    parseError.value = '无法识别的 URL 格式，示例：https://e-hentai.org/g/12345/abcdef1234/'
    return
  }
  const [, gid, token] = m
  router.push({ path: `/gallery/${gid}/translate`, query: { token } })
}

function handleKeydown(e) {
  if (e.key === 'Enter') handleGo()
}
</script>

<template>
  <div class="tl-container">
    <div class="tl-card">
      <div class="tl-eyebrow">Translation Workbench</div>
      <h2 class="tl-title">通过 URL 进入翻译</h2>
      <p class="tl-desc">输入 E-Hentai / ExHentai 画廊 URL，解析后直接进入翻译工作台</p>

      <div class="tl-form">
        <input
          ref="urlInputRef"
          v-model="urlInput"
          type="text"
          class="tl-input"
          placeholder="https://e-hentai.org/g/12345/abcdef1234/"
          autocomplete="off"
          spellcheck="false"
          @keydown="handleKeydown"
        />
        <button class="gt-btn gt-btn-primary" @click="handleGo">进入</button>
      </div>

      <p v-if="parseError" class="tl-error">{{ parseError }}</p>

      <p class="tl-hint">支持 e-hentai.org 和 exhentai.org 链接</p>
    </div>
  </div>
</template>

<style scoped>
.gt-btn {
  padding: .55rem 1.1rem;
  border-radius: 8px;
  border: none;
  font-size: .9rem;
  cursor: pointer;
  font-weight: 600;
  transition: opacity .15s;
}
.gt-btn-primary {
  background: var(--primary-color, #6366f1);
  color: #fff;
}
.gt-btn-primary:hover { opacity: .85; }

/* URL 输入页样式 */
.tl-container {
  min-height: calc(100vh - var(--app-nav-height, 53px));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem 1rem;
}
.tl-card {
  background: var(--surface-color, #1e293b);
  border-radius: 14px;
  padding: 2.5rem 2.5rem 2rem;
  max-width: 560px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: .75rem;
  box-shadow: 0 4px 24px rgba(0,0,0,.25);
}
.tl-eyebrow {
  font-size: .75rem;
  letter-spacing: .08em;
  text-transform: uppercase;
  opacity: .5;
}
.tl-title {
  font-size: 1.4rem;
  font-weight: 700;
  margin: 0;
}
.tl-desc { font-size: .875rem; opacity: .65; margin: 0; }
.tl-form {
  display: flex;
  gap: .5rem;
  margin-top: .25rem;
}
.tl-input {
  flex: 1;
  padding: .6rem .9rem;
  border-radius: 8px;
  border: 1.5px solid var(--border-color, #334155);
  background: var(--bg-color, #0f172a);
  color: var(--text-color, #f1f5f9);
  font-size: .9rem;
  font-family: inherit;
  outline: none;
  transition: border-color .15s;
  min-width: 0;
}
.tl-input:focus { border-color: var(--primary-color, #6366f1); }
.tl-error { color: #f87171; font-size: .85rem; margin: 0; }
.tl-hint { font-size: .8rem; opacity: .4; margin: 0; }
</style>
