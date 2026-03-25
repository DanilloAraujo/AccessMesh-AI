param name string
param location string
param tags object

resource speech 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'SpeechServices'
  sku: {
    name: 'S0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: name
  }
}

output id string = speech.id
output endpoint string = speech.properties.endpoint
#disable-next-line outputs-should-not-contain-secrets
output key string = speech.listKeys().key1
