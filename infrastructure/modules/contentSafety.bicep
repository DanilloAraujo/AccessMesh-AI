param name string
param location string
param tags object

resource contentSafety 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'ContentSafety'
  sku: {
    name: 'S0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: name
  }
}

output id string = contentSafety.id
output endpoint string = contentSafety.properties.endpoint
#disable-next-line outputs-should-not-contain-secrets
output key string = contentSafety.listKeys().key1
