<template>
  <div id="app-container">
    <router-view />
  </div>
</template>

<script setup>
// Simple app container without complex providers
</script>

<style>
#app-container {
  width: 100%;
  height: 100vh;
  background-color: var(--color-bg-primary);
  color: var(--color-text-primary);
}
</style>
