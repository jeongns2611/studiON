<script setup lang="ts">
import logoDark from '@/assets/logo_dark.png'
import ProfileSetupForm from './components/ProfileSetupForm.vue'

</script>

<template>
  <main class="min-h-screen bg-[#131313] text-[#e5e2e1]">
    <header class="relative z-10 flex items-center justify-between border-b border-white/10 px-6 py-5 md:px-10">
      <div class="flex items-center gap-3">
        <img
          :src="logoDark"
          alt="StudiON"
          class="h-20 w-auto"
        >
      </div>
    </header>

    <section class="relative overflow-hidden">
      <!-- glow -->
      <div class="pointer-events-none absolute inset-0 -z-10">
        <div
          class="absolute -left-40 top-0 h-[70vh] w-[70vh] rounded-full blur-[140px] bg-[#FF3DCB]/15"
        />
        <div
          class="absolute -right-32 bottom-0 h-[55vh] w-[55vh] rounded-full blur-[120px] bg-[#FF3DCB]/15"
        />
      </div>

      <!-- grid -->
      <div class="absolute inset-0 -z-10 opacity-30">
        <div
          class="h-full w-full"
          style="
            background-image:
              linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(255,255,255,0.05) 1px, transparent 1px);
            background-size: 32px 32px;
          "
        />
      </div>

      <div class="mx-auto flex max-w-3xl flex-col px-6 pb-16 pt-6 md:px-10">
        <ProfileSetupForm />
      </div>
    </section>
  </main>
</template>