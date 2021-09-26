<template>
  <v-app>
    <v-app-bar app color="info" elevation="8" class="white--text">
      <h3 class="ma-4">Kimi mo Sodayo (mini)</h3>
    </v-app-bar>

    <v-divider inset></v-divider>
    
    <v-main>
      <v-container class="ma-4">
        <v-row class="d-inline-flex flex-row align-start justify-start">
          <quota   v-bind:width="340" class="ma-4"/>
          <runtime v-bind:width="340" class="ma-4"/>
          <realloc v-bind:width="340" class="ma-4"/>
        </v-row>
      </v-container>
    </v-main>

    <v-footer app padless>
      <v-container class="text-right">
        Powered by Armit @ 2021/09/24
      </v-container>
    </v-footer>

  </v-app>
</template>

<script>
import Quota from './components/Quota.vue';
import Realloc from './components/Realloc.vue';
import Runtime from './components/Runtime.vue';

export default {
  name: 'App',
  components: {
    Quota,
    Realloc,
    Runtime,
  },
};
</script>
