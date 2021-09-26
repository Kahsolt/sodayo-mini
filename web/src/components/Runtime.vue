<template>
  <v-card :width=width>

    <v-list-item>
      <v-list-item-content>
        <span class="text-overline mb-4"> Runtime Info </span>
        
        <v-treeview
          transition
          dense
          open-all
          hoverable
          :open.sync="tv_root_ids"
          :items="tv_runtime_info"
        ></v-treeview>

      </v-list-item-content>
    </v-list-item>

  </v-card>
</template>

<script>
import bus from '../plugins/bus'
import hp from '../plugins/settings'

export default {
  name: 'Runtime',
  props: { width: Number },
  data() {
    return {
      runtime_info: [ ],
      overquota_users: [ ],
      tv_runtime_info: [ ],
      tv_root_ids: [ ],
    }
  },
  methods: {
    redraw() {
      this.tv_root_ids.length = 0
      this.tv_runtime_info.length = 0
      let id = 1
      let data = this.runtime_info
      for (let hostname in data) {
        this.tv_root_ids.push(id)
        let d = {
          id: id++,
          name: hostname,
          children: [ ],
        }
        for (let gpu_id in data[hostname]) {
          let users = data[hostname][gpu_id]
          let line = '[' + gpu_id + ']: '  + users.sort()
          d.children.push({name: line})
        }
        this.tv_runtime_info.push(d)
      }
    },
    refresh() {
      this.axios.get('/runtime')
                .then(res => {
                  let r = res.data
                  if (r.ok) {
                    this.runtime_info = r.data
                    this.redraw()

                    let idle_gpu_count = 0
                    for (let hostname in r.data)
                      for (let gpu_id in r.data[hostname])
                        if (r.data[hostname][gpu_id].length == 0)
                          idle_gpu_count++
                    bus.$emit('idle_gpu_count', idle_gpu_count)
                  } else {
                    let msg = '[runtime] error: ' + r.reason
                    console.log(msg)
                  }
                })
                .catch(err => console.log(err))
    }
  },
  beforeMount() {
    this.refresh()
    setInterval(this.refresh, 1000 * hp.REFRESH_INTERVAL)

    bus.$on('overquota_users', (val) => {
      this.overquota_users = val
      this.redraw()
    })
  }
}
</script>

<style>
.v-treeview--dense .v-treeview-node__root {
  min-height: 40px;
}
</style>