<script setup lang="ts">
import { Button } from '@/shared/ui/button'

defineEmits<{
  click: []
}>()
</script>

<template>
  <Button type="button" @click="$emit('click')">
    초대코드 생성
  </Button>
</template>
