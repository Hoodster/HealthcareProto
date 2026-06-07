targetScope = 'resourceGroup'

// ─── Parameters ───────────────────────────────────────────────────────────────

@description('Name of the azd environment (used in resource naming and tagging)')
param environmentName string

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('PostgreSQL administrator username')
param dbAdminUsername string = 'pgadmin'

@description('PostgreSQL administrator password')
@secure()
param dbAdminPassword string

@description('Azure region for PostgreSQL (must be offer-available on this subscription).')
param dbLocation string = 'northeurope'

@description('OpenAI API key for LLM-based features')
@secure()
param openAiApiKey string

// ─── Variables ────────────────────────────────────────────────────────────────

// Unique suffix for all resource names (az{prefix}{token})
var resourceToken = uniqueString(subscription().id, resourceGroup().id, location, environmentName)
var postgresResourceToken = uniqueString(subscription().id, resourceGroup().id, dbLocation, environmentName)

var tags = {
  'azd-env-name': environmentName
  project: 'healthcare-proto'
}

// ─── User-Assigned Managed Identity ──────────────────────────────────────────

resource managedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'azmi${resourceToken}'
  location: location
  tags: tags
}

// ─── Log Analytics Workspace ──────────────────────────────────────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'azlaw${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ─── Application Insights ─────────────────────────────────────────────────────

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'azai${resourceToken}'
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ─── Key Vault ────────────────────────────────────────────────────────────────

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'azkv${resourceToken}'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    // RBAC auth — no legacy access policies
    enableRbacAuthorization: true
    // Allow access from all networks so App Service KV references work
    publicNetworkAccess: 'Enabled'
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    // DO NOT disable purge protection
    enablePurgeProtection: true
  }
}

// Key Vault Secrets Officer — MI can create/update secrets during provisioning
var kvSecretsOfficerRoleId = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
resource kvSecretsOfficerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, kvSecretsOfficerRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsOfficerRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets User — App Service reads secrets at runtime
var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'
resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, managedIdentity.id, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Container Registry ───────────────────────────────────────────────────────
// DO NOT enable anonymous pull (per security rules)

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: 'azcr${resourceToken}'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// AcrPull — MI can pull images into App Service
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, managedIdentity.id, acrPullRoleId)
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPullRoleId)
    principalId: managedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── PostgreSQL Flexible Server ───────────────────────────────────────────────

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: 'azpg${postgresResourceToken}'
  location: dbLocation
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '17'
    administratorLogin: dbAdminUsername
    administratorLoginPassword: dbAdminPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

// Allow traffic from Azure services (IP 0.0.0.0)
resource postgresFirewallAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: postgresServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// Application database (not named 'postgres' — that's built-in)
resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: postgresServer
  name: 'healthcare_db'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Store the PostgreSQL connection URL in Key Vault
// Depends on the Secrets Officer role being ready first
resource kvSecretDbUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'db-url'
  properties: {
    value: 'postgresql+psycopg2://${dbAdminUsername}:${dbAdminPassword}@${postgresServer.properties.fullyQualifiedDomainName}:5432/healthcare_db?sslmode=require'
  }
  dependsOn: [kvSecretsOfficerRole]
}

// ─── App Service Plan (Linux) ─────────────────────────────────────────────────

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'azsp${resourceToken}'
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    // MUST be true for Linux
    reserved: true
  }
}

// ─── App Service (Web App for Containers) ────────────────────────────────────

resource webApp 'Microsoft.Web/sites@2024-04-01' = {
  name: 'azap${resourceToken}'
  location: location
  kind: 'app,linux,container'
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentity.id}': {}
    }
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    // Use user-assigned MI for Key Vault secret references
    keyVaultReferenceIdentity: managedIdentity.id
    siteConfig: {
      // Container image — azd overwrites this on deploy
      linuxFxVersion: 'DOCKER|${containerRegistry.properties.loginServer}/healthcare-proto/api:latest'
      // Pull from ACR using managed identity (no admin credentials)
      acrUseManagedIdentityCreds: true
      acrUserManagedIdentityID: managedIdentity.properties.clientId
      appSettings: [
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${containerRegistry.properties.loginServer}'
        }
        {
          // Key Vault reference — App Service resolves this at runtime via MI
          name: 'DB_URL'
          value: '@Microsoft.KeyVault(VaultName=${keyVault.name};SecretName=db-url)'
        }
        {
          name: 'API_OPENAI'
          value: openAiApiKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          // Tell App Service which port the container listens on
          name: 'WEBSITES_PORT'
          value: '8000'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'false'
        }
      ]
      cors: {
        allowedOrigins: ['*']
        supportCredentials: false
      }
    }
  }
  dependsOn: [
    kvSecretsUserRole
    acrPullRole
    kvSecretDbUrl
  ]
}

// Diagnostic settings — stream logs to Log Analytics
resource webAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'diagnostics'
  scope: webApp
  properties: {
    workspaceId: logAnalytics.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServiceAppLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// ─── Outputs (consumed by azd) ────────────────────────────────────────────────

output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.properties.loginServer
output SERVICE_API_NAME string = webApp.name
output SERVICE_API_RESOURCE_GROUP string = resourceGroup().name
output WEB_APP_URL string = 'https://${webApp.properties.defaultHostName}'
output POSTGRES_SERVER_NAME string = postgresServer.name
output KEY_VAULT_NAME string = keyVault.name
