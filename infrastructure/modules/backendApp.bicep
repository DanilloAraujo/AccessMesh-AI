param name string
param location string
param containerAppsEnvId string
param acrLoginServer string
param acrName string
param keyVaultName string
param appInsightsConnectionString string
param corsOrigins string
param tags object

// Fetch the ACR credentials at deployment time so the Container App can pull images
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource backendApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    managedEnvironmentId: containerAppsEnvId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        corsPolicy: {
          allowedOrigins: split(corsOrigins, ',')
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: true
        }
      }
      registries: [
        {
          server: acrLoginServer
          username: acr.listCredentials().username
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acr.listCredentials().passwords[0].value
        }
        {
          name: 'appinsights-connection-string'
          value: appInsightsConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          // Update this image tag after your first build & push to ACR
          image: '${acrLoginServer}/accessmesh-backend:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'AZURE_KEYVAULT_URL'
              value: 'https://${keyVaultName}.vault.azure.net/'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
            {
              name: 'CORS_ORIGINS'
              value: corsOrigins
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

// Grant the Container App Managed Identity Key Vault Secrets User role
var kvSecretsUserRole = '4633458b-17de-408a-b874-0445c86b69e6' // Key Vault Secrets User
resource kvRef 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kvRef.id, backendApp.id, kvSecretsUserRole)
  scope: kvRef
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRole)
    principalId: backendApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

output id string = backendApp.id
output url string = 'https://${backendApp.properties.configuration.ingress.fqdn}'
output principalId string = backendApp.identity.principalId
