<template>
  <div large class="text-center">
    <v-snackbar large v-model="is_show" :timeout="timeout" :color="color">
      {{ message }}

      <template v-slot:action="{ attrs }">
        <v-btn icon color="white--text" v-bind="attrs" @click="is_show = false"> x </v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script>
import bus from '../plugins/bus'

export default {
  name: 'MessageBox',
  data: () => ({
    is_show: false,
    message: '',
    timeout: 5000,
    color: 'red',
  }),
  beforeMount() {
    bus.$on('messagebox' , (msg, ok) => {
      this.color = ok ? 'green' : 'red'
      this.message = (ok ? 'Success: ' : 'Error: ') + msg
      this.is_show = true
    })
  }
}
</script>
