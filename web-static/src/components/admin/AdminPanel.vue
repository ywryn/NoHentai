<script setup>
import RecordEditor from './RecordEditor.vue'
import ServiceSettings from './ServiceSettings.vue'
import TaskManager from './TaskManager.vue'
import WorkspaceOverview from './WorkspaceOverview.vue'
import AccountSettings from './AccountSettings.vue'
import BackupManager from './BackupManager.vue'
import AuditHistory from './AuditHistory.vue'
defineProps({section:{type:String,required:true}})
</script>
<template><RecordEditor v-if="['galleries','daily','printed'].includes(section)" :kind="section==='galleries'?'gallery':section==='printed'?'book':'daily'" /><ServiceSettings v-else-if="['services','translate','credentials'].includes(section)" /><TaskManager v-else-if="section==='tasks'" /><AccountSettings v-else-if="section==='account'" /><BackupManager v-else-if="section==='backups'" /><AuditHistory v-else-if="section==='history'" /><WorkspaceOverview v-else :health-only="section==='health'" /></template>
