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
            <v-btn icon color="primary" @click="gpu_count < idle_gpu_count ? gpu_count++ : gpu_count">
              <v-icon>mdi-plus-circle</v-icon>
            </v-btn>
          </span>

          <span class="float-right mx-3">
            <v-progress-circular v-if="is_busy" indeterminate color="error"></v-progress-circular>
            <v-btn v-else @click="submit()" color="error"> Submit! </v-btn>
          </span>

        </v-form>

      </v-list-item-content>
    </v-list-item>

  </v-card>
</template>

<script>
import bus from '../plugins/bus'

export default {
  name: 'Realloc',
  props: { width: Number },
  data() {
    return {
      is_busy: false,
      idle_gpu_count: -1,
      username: '',
      password: '',
      gpu_count: 1,
    }
  },
  methods: {
    submit() {
      let reqdata = {
        username: this.username,
        password: this.password,
        gpu_count: this.gpu_count,
      }
      this.is_busy = true
      this.axios
          .post('/realloc', reqdata)
          .then(res => {
            let r = res.data
            if (r.ok) {
              let hostname = r.data.hostname
              let gpu_ids = r.data.gpu_ids
              let msg = '[' + hostname + ']: ' + gpu_ids.toString()
              alert(msg); console.log(msg)
            } else {
              let msg = '[realloc] error: ' + r.reason
              alert(msg); console.log(msg)
              this.refresh()
            }
          })
          .catch(err => console.log(err))
      this.is_busy = false
    },
  },
  beforeMount() {
      bus.$on('idle_gpu_count', (val) => {
        this.idle_gpu_count = val;
      })
  },
}
</script>
