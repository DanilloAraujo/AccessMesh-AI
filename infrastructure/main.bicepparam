using './main.bicep'

param env = 'dev'
param location = 'eastus'
param projectName = 'accessmesh'

// Replace with your AAD object ID:
//   az ad signed-in-user show --query id -o tsv
param kvAdminObjectId = '<YOUR_AAD_OBJECT_ID>'

param corsOrigins = 'http://localhost:5173'
