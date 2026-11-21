<script setup>
import AppIcon from './ui/AppIcon.vue'
defineProps({ label:String, prefix:String, passwordLoading:Boolean, passwordError:String })
const passwordInput = defineModel({type:String,default:''})
defineEmits(['verify','back'])
</script>
<template>
  <div class="gt-overlay">
    <div class="gt-pwd-dialog">

      <h2 class="gt-pwd-title">访问验证</h2>

      <form class="gt-pwd-form" @submit.prevent="$emit('verify')">
        <input
          :id="prefix+'-access-password'"
          :aria-label="label"
          autocomplete="current-password"
          :aria-invalid="Boolean(passwordError)"
          :aria-describedby="passwordError ? prefix+'-access-error' : undefined"
          required
          v-model="passwordInput"
          type="password"
          placeholder="输入密码"
          class="gt-pwd-input"
          :disabled="passwordLoading"
          autofocus
        />
        <button
          class="gt-btn gt-btn-primary"
          :disabled="passwordLoading || !passwordInput"
          type="submit"
        >
          {{ passwordLoading ? '验证中...' : '进入' }}
        </button>
      </form>
      <p v-if="passwordError" :id="prefix+'-access-error'" class="gt-pwd-error" role="alert">{{ passwordError }}</p>
      <button class="gt-pwd-back" @click="$emit('back')"><AppIcon name="arrow-left" :size="18" /> 返回</button>
    </div>
  </div>

</template>
<style scoped>
.gt-overlay {
  position: fixed;
  inset: 0;
  background: var(--bg-color);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.gt-pwd-dialog {
  background: var(--row-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 32px;
  max-width: 400px;
  width: calc(100vw - 48px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gt-pwd-eyebrow {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--primary-color);
}

.gt-pwd-title {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-color);
}

.gt-pwd-desc {
  margin: 0;
  font-size: 13px;
  color: var(--muted-color);
}

.gt-pwd-form {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.gt-pwd-input {
  flex: 1;
  height: 38px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--bg-color);
  color: var(--text-color);
  font-size: 14px;
  font-family: inherit;
  transition: border-color var(--dur-fast) var(--ease-out);
}
.gt-pwd-input:focus { border-color: var(--primary-color); }
.gt-pwd-input:disabled { opacity: 0.5; }

.gt-pwd-error {
  margin: 0;
  font-size: 12px;
  color: var(--danger-color);
}

.gt-pwd-back {
  background: none;
  border: none;
  color: var(--muted-color);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
  text-align: left;
  margin-top: 4px;
  transition: color var(--dur-fast);
}
.gt-pwd-back:hover { color: var(--text-color); }

.gt-btn {
  height: 32px;
  padding: 0 14px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--row-bg);
  color: var(--text-color);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--dur-fast), color var(--dur-fast), border-color var(--dur-fast), opacity var(--dur-fast);
}
.gt-btn:hover:not(:disabled) { background: var(--hover-bg); border-color: var(--muted-color); }
.gt-btn:disabled { opacity: 0.4; cursor: default; }

.gt-btn-primary {
  background: var(--primary-color);
  border-color: var(--primary-color);
  color: #fff;
  font-weight: 600;
}
.gt-btn-primary:hover:not(:disabled) { background: var(--primary-color-hover); border-color: var(--primary-color-hover); }

.gt-pwd-input{min-width:0}
</style>
