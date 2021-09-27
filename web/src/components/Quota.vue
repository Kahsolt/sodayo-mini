<template>
  <v-card :width=width>

    <v-list-item>
      <v-list-item-content>
        <span class="text-overline mb-4"> Quota remnants </span>
        
        <v-simple-table dense>
          <template v-slot:default>
            <thead>
              <tr>
                <th class="text-left"> user </th>
                <th class="text-left"> remnants </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(val, key, idx) in quota_info"
                :key="idx"
              >
                <td> {{ key }} </td>

                <td v-if="val <= 0">        <strong class="red--text">   {{ Number(val).toFixed(2) }}</strong> hours </td>
                <td v-else-if="val <= 150"> <strong class="orange--text">{{ Number(val).toFixed(2) }}</strong> hours </td>
                <td v-else>                 <strong class="green--text"> {{ Number(val).toFixed(2) }}</strong> hours </td>
              </tr>
            </tbody>
          </template>
        </v-simple-table>

      </v-list-item-content>
    </v-list-item>

  </v-card>
</template>

<script>
import hp from '../plugins/settings'
import bus from '../plugins/bus'

export default {
  name: 'Quota',
  props: { width: Number },
  data() {
    return {
      quota_info: { }
    }
  },
  methods: {
    refresh() {
      console.log('[Quota.refresh]')
      
      this.axios
          .get('/quota')
          .then(res => {
            let r = res.data
            if (r.ok) {
              this.quota_info = r.data
            } else {
              bus.$emit('messagebox', r.reason, false)
              let msg = '[quota] error: ' + r.reason
              console.log(msg)
            }
          })
          .catch(err => console.log(err))
    }
  },
  beforeMount() {
    this.refresh()
    setInterval(this.refresh, 1000 * hp.REFRESH_INTERVAL)

    bus.$on('refresh', () => this.refresh())
  },
}
</script>
