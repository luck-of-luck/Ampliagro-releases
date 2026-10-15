# Alta Frequência - Pontos Críticos do Sistema

## 1. Dashboard & Presets (Top Priority)
- **Presets Management** (`base-ia`, `amplia`, `chamado-amplia`)
  - Used by all users daily
  - State isolation critical: prevents ghost presets from corrupting active state
  - Blocklist handling for custom presets (`custom-*`)
- **Widget Configuration**
  - Layout sync across devices
  - Theme switching (light/dark)
  - Custom widget ordering
- **Active Preset Selection**
  - Automatic selection of `active_preset`
  - Fallback logic when preset is removed

## 2. Onboarding Flow
- **New User Registration**
  - Property creation wizard
  - Profile setup (role assignment: produtor, operario, agrônomo, etc.)
  - Initial dashboard population
- **Property Management**
  - Multi-tenancy support (each property isolated)
  - Custom field addition/modification
- **Authentication**
  - Login flow
  - Role-based access control (RBAC)

## 3. Core Domain Entities (High Frequency)
- **Talhões** (Fields)
  - Creation, modification, deletion
  - Geo-referencing (lat/long)
- **Culturas** (Crops)
  - Variety selection
  - Growth cycle management
- **Safras** (Harvests)
  - Harvest scheduling
  - Yield estimation
- **Lançamentos Financeiros** (Financial Transactions)
  - Cost tracking
  - Revenue reconciliation
- **Propriedades** (Properties)
  - Multi-tenant isolation
  - User assignment

## 4. Map & GIS Features
- **OSM Tiles** (OpenStreetMap)
  - Interactive mapping
  - Real-time data overlays
  - CSP connectivity required
- **Leaflet Integration**
  - Map rendering
  - Widget integration (talhões, culturas, safras)

## 5. AI & MCP Integration
- **AI Assistant** (`app/amplia_mcp`)
  - On-demand AI responses
  - Context preservation
- **Sandbox Environment**
  - Local AI testing
  - Sandbox API endpoints

## 6. Performance & Scalability
- **Caching Strategy**
  - PWA Service Worker (`sw.js`)
  - Cache invalidation policies
- **Database Queries**
  - Aggregation for dashboards
  - Real-time updates

## Key Metrics
| Component | Usage Frequency | Impact if Down |
|-----------|-----------------|----------------|
| Dashboard/Presets | Daily | High |
| Onboarding | New Users | Medium |
| Talhões | Daily | High |
| Culturas | Daily | High |
| Safras | Weekly | Medium |
| Financials | Daily | High |
| Maps/OSM | Daily | Medium |
| AI/MCP | Occasional | Low |