param name string
param location string
param tags object

resource translator 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'TextTranslation'
  sku: {
    name: 'F0' // Free tier — 2M chars/month. Change to S1 for production.
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: name
  }
}

output id string = translator.id
output endpoint string = 'https://api.cognitive.microsofttranslator.com'
#disable-next-line outputs-should-not-contain-secrets
output key string = translator.listKeys().key1
