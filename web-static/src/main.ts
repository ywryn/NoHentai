import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import PrimeVue from 'primevue/config';
import Aura from '@primevue/themes/aura';
import router from './router'; // 引入路由配置


const app = createApp(App);
app.use(PrimeVue, {
    theme: {
        preset: Aura,
        options: {
            darkModeSelector: '.my-app-dark',
        }
    }
});

import Button from "primevue/button"
import Tooltip from 'primevue/tooltip'; // 引入 Tooltip 指令
app.component('Button', Button);

app.use(router); // 挂载路由
// 注册 Tooltip 全局指令
app.directive('tooltip', Tooltip);

// Resolve the initial route before rendering public or immersive navigation.
router.isReady().then(() => app.mount('#app'))
