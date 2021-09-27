const settings = {
  // global baseUrl of `axios` requests
  // REFER: sodayo `setting.API_BASE`
  API_BASE: 'http://210.28.134.114:25101',
  
  // global timeout of `axios` requests
  NETWORK_TIMEOUT: 15,

  // auto refresh data (in seconds)
  // REFER: sodayo `setting.FORCE_SYNC_DEADTIME`
  FORCE_SYNC_DEADTIME: 10,

  // auto refresh data (in seconds)
  // REFER: sodayo `setting.AUTO_SYNC_INTERVAL`
  REFRESH_INTERVAL: 60 * 10,

  // max alloc gpu count at once
  // REFER: sodayo `setting.MAX_REALLOC_COUNT`
  MAX_REALLOC_COUNT: 8,

}

export default settings
