param name string
param location string
param tags object

resource wps 'Microsoft.SignalRService/webPubSub@2023-08-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Free_F1'
    tier: 'Free'
    capacity: 1
  }
  properties: {
    publicNetworkAccess: 'Enabled'
  }
}

resource hub 'Microsoft.SignalRService/webPubSub/hubs@2023-08-01-preview' = {
  parent: wps
  name: 'accessmesh'
  properties: {
    anonymousConnectPolicy: 'deny'
  }
}

output id string = wps.id
#disable-next-line outputs-should-not-contain-secrets
output connectionString string = wps.listKeys().primaryConnectionString
output endpoint string = 'https://${wps.properties.hostName}'
