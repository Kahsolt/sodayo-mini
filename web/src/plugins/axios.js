import axios from 'axios'
import hp from '../plugins/settings'

export default axios.create({
  baseURL: hp.API_BASE,
  timeout: 5000
})
