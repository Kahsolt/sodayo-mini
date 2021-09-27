<template>
  <v-card :width=width>

    <v-list-item>
      <v-list-item-content>
        <div class="text-overline"> ReAlloc </div>
        <v-divider></v-divider>



        <v-card-subtitle class="text-center grey--text">
          <p v-if="idle_gpu_count <= 1">      currently <strong class="red--text">   {{ idle_gpu_count }}</strong> GPUs are free :) </p>
          <p v-else-if="idle_gpu_count <= 4"> currently <strong class="orange--text">{{ idle_gpu_count }}</strong> GPUs are free :) </p>
          <p v-else>                          currently <strong class="green--text"> {{ idle_gpu_count }}</strong> GPUs are free :) </p>
        </v-card-subtitle>

        <v-spacer></v-spacer>

        <v-form ref="form" lazy-validation>

          <span>username: </span>
          <v-text-field v-model="username" type="text"></v-text-field>

          <span>password: </span>
          <v-text-field v-model="password" type="password"></v-text-field>

          <span>gpu count: </span>
          <span class="mx-1">
            <v-btn icon color="primary" @click="gpu_count > 1 ? gpu_count-- : gpu_count">
              <v-icon>mdi-minus-circle</v-icon>
            </v-btn>
            <span class="text-center">
              {{ gpu_count }}
            </span>
            <v-btn icon color="primary" @click="gpu_count < MAX_REALLOC_COUNT ? gpu_count++ : gpu_count">
              <v-icon>mdi-plus-circle</v-icon>
            </v-btn>
          </span>

          <span class="float-right mx-3">
            <v-btn color="error" :loading="is_submit" @click="submit()"> Submit! </v-btn>
          </span>

        </v-form>

      </v-list-item-content>
    </v-list-item>

  </v-card>
</template>

<script>
import { encode } from 'js-base64'
import hp from '../plugins/settings'
import bus from '../plugins/bus'

export default {
  name: 'Realloc',
  props: { width: Number },
  data() {
    return {
      MAX_REALLOC_COUNT: hp.MAX_REALLOC_COUNT,

      loader: null,
      is_submit: false,

      idle_gpu_count: -1,
      username: '',
      password: '',
      gpu_count: 1,
    }
  },
  methods: {
    submit() {
      console.log('[Realloc.submit]')
      this.loader = 'is_submit'

      let reqdata = {
        username: encode(this.username),
        password: encode(this.password),
        gpu_count: this.gpu_count,
      }

      bus.$emit('set_overlay', true)
      this.axios
          .post('/realloc', reqdata)
          .then(res => {
            let r = res.data
            if (r.ok) {
              let hostname = r.data.hostname
              let gpu_ids = r.data.gpu_ids
              let msg = '[' + hostname + ']: ' + gpu_ids.toString()

              bus.$emit('messagebox', msg, true)
              console.log('[realloc] ok: ' + msg)

              setTimeout(() => bus.$emit('refresh'), 3000)
            } else {
              bus.$emit('messagebox', r.reason, false)
              console.log('[realloc] error: ' + r.reason)
            }
          })
          .catch(err => console.log(err))
          .finally(() => bus.$emit('set_overlay', false))
    },
  },
  beforeMount() {
    bus.$on('idle_gpu_count', (val) => (this.idle_gpu_count = val))
  },
  watch: {
    loader () {
      const l = this.loader
      this[l] = !this[l]
      setTimeout(() => (this[l] = false), 5000)
      this.loader = null
    },
  },
}
</script>
