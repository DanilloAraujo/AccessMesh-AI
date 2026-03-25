param name string
param location string
param tags object

// Azure OpenAI is not available in all regions — eastus and westeurope are the most common choices.
resource openAi 'Microsoft.CognitiveServices/accounts@2023-10-01-preview' = {
  name: name
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: name
  }
}

// GPT-4o-mini — used for gesture classification and summarisation
resource gpt4oMiniDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-10-01-preview' = {
  parent: openAi
  name: 'gpt-4o-mini'
  sku: {
    name: 'Standard'
    capacity: 10 // TPM × 1 000 — adjust per quota
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o-mini'
      version: '2024-07-18'
    }
    versionUpgradeOption: 'OnceCurrentVersionExpired'
  }
}

output id string = openAi.id
output endpoint string = openAi.properties.endpoint
#disable-next-line outputs-should-not-contain-secrets
output key string = openAi.listKeys().key1
