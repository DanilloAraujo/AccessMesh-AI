param name string
param location string
@description('Object ID of the principal that will receive Key Vault Administrator role.')
param adminObjectId string
param tags object

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: false // set true for prod
    publicNetworkAccess: 'Enabled'
  }
}

// Grant the deploying principal Key Vault Administrator
var kvAdminRole = '00482a5a-887f-4fb3-b363-3b7fe8e74483' // Key Vault Administrator
resource kvAdminAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, adminObjectId, kvAdminRole)
  scope: kv
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvAdminRole)
    principalId: adminObjectId
    principalType: 'User'
  }
}

output id string = kv.id
output name string = kv.name
output uri string = kv.properties.vaultUri
