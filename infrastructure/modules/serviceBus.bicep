param namespaceName string
param location string
param tags object

resource sbNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {}
}

resource topic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'accessmesh-events'
  properties: {
    defaultMessageTimeToLive: 'P1D'
    enableBatchedOperations: true
  }
}

// Send+Listen rule used by the backend
resource authRule 'Microsoft.ServiceBus/namespaces/AuthorizationRules@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'accessmesh-app'
  properties: {
    rights: ['Send', 'Listen']
  }
}

output id string = sbNamespace.id
#disable-next-line outputs-should-not-contain-secrets
output connectionString string = authRule.listKeys().primaryConnectionString
