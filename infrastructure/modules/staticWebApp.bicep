param name string
param location string
param tags object

// Azure Static Web Apps only support a limited set of locations for the resource itself.
// The frontend assets are distributed via CDN globally.
resource swa 'Microsoft.Web/staticSites@2023-12-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    stagingEnvironmentPolicy: 'Disabled'
    allowConfigFileUpdates: true
    buildProperties: {
      appLocation: 'frontend'
      outputLocation: 'dist'
      appBuildCommand: 'npm run build'
    }
  }
}

output id string = swa.id
output defaultHostname string = swa.properties.defaultHostname
output deploymentToken string = swa.listSecrets().properties.apiKey
