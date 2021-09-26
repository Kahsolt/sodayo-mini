<template>
  <v-app>
    <v-overlay :value="is_overlay" class="text-center">
      <v-progress-circular
        indeterminate
        color="red"
        :size="72"
        :width="10"
      ></v-progress-circular>
    </v-overlay>

    <message-box></message-box>

    <v-app-bar app color="info" elevation="8" class="white--text">
      <h3 class="ma-4">Kimi mo Sodayo (mini)</h3>
      <div class="float-right">
        <v-tooltip bottom>
          <template v-slot:activator="{ on, attrs }">
            <v-btn icon large color="red" v-bind="attrs" v-on="on" :loading="is_sync" @click="sync()">
              <v-icon>mdi-sync</v-icon>
            </v-btn>
          </template>
          <span>instant forced-sync</span>
        </v-tooltip>

        <v-tooltip bottom>
          <template v-slot:activator="{ on, attrs }">
            <v-btn icon large color="green lighten-2" v-bind="attrs" v-on="on" :loading="is_refresh" @click="refresh()">
              <v-icon>mdi-reload</v-icon>
            </v-btn>
          </template>
          <span>refresh by latest auto-sync</span>
        </v-tooltip>
      </div>
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
import MessageBox from './components/MessageBox.vue';
import Quota from './components/Quota.vue';
import Runtime from './components/Runtime.vue';
import Realloc from './components/Realloc.vue';
import bus from './plugins/bus'
import hp from './plugins/settings'

export default {
  name: 'App',
  components: {
    MessageBox,
    Quota,
    Runtime,
    Realloc,
  },
  data() {
    return {
      loader: null,
      is_sync: false,
      is_refresh: false,

      is_overlay: false,
    }
  },
  methods: {
    refresh() {
      console.log('[App.refresh]')
      this.loader = 'is_refresh'

      bus.$emit('refresh')
      bus.$emit('messagebox', 'ok', true)
    },
    sync() {
      console.log('[App.sync]')
      this.loader = 'is_sync'

      bus.$emit('set_overlay', true)
      this.axios
          .put('/sync')
          .then(res => {
            let r = res.data
            if (r.ok) {
              bus.$emit('refresh')
              bus.$emit('messagebox', 'ok', true)
            } else {
              bus.$emit('messagebox', r.reason, false)
              console.log('[sync] error: ' + r.reason)
            }
          })
          .catch(err => console.log(err))
          .finally(() => {
            bus.$emit('set_overlay', false)
          })
    },
  },
  beforeMount() {
    bus.$on('set_overlay', (val) => {
      this.is_overlay = val
    })
  },
  watch: {
    loader () {
      const l = this.loader
      this[l] = !this[l]
      setTimeout(() => (this[l] = false), 1000 * hp.SYNC_DEADTIME)
      this.loader = null
    },
  },
};
</script>
