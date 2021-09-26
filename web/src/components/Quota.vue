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
import bus from '../plugins/bus'
import hp from '../plugins/settings'

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
      this.axios.get('/quota')
                .then(res => {
                  let r = res.data
                  if (r.ok) {
                    this.quota_info = r.data

                    let overquota_users = [ ]
                    for (let user in r.data)
                      if (r.data[user] <= 0)
                        overquota_users.push(user)
                    if (overquota_users.length > 0)
                      bus.$emit('overquota_users', overquota_users)
                  } else {
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
  },
}
</script>
