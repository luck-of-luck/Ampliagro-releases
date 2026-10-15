# Estado Isolation - Dashboard & Presets Protection

## Overview
Ensures that dashboard state (widget configurations, active presets, layout) is protected from corruption by:
- Ghost presets (removed from UI but still in DB)
- Concurrent modifications
- Backend-to-frontend race conditions

## Current Implementation

### Preset Permission System
- **Immutable Base Presets**: `base-ia`, `amplia`, `chamado-amplia`
- **Custom Presets**: `custom-*` (user-defined)
- **Blocklist**: Certain custom presets are blocked from activation

### Active Preset Logic
- `active_preset` field in `DashboardUserState` determines which preset is currently active
- On startup, selects the first permitted active preset
- When a preset is removed, triggers cleanup of dependent widgets

## Risk Areas
1. **Ghost Preset Persistence** - Removed presets still exist in DB and can be accidentally activated
2. **Concurrent Edits** - Multiple users editing the same preset simultaneously
3. **Layout Corruption** - Changing active preset affects entire dashboard layout
4. **Cache Invalidation** - Old widget configurations not cleared when preset changes

## Mitigation Strategies

### 1. Immediate Fixes
- **Validate active preset existence** before setting `active_preset`
- **Soft delete** ghost presets instead of hard removal
- **Transactional state updates** - Use DB transactions for preset + state changes

### 2. Long-term Improvements
- **Event-driven state synchronization** - Publish state changes via Kafka/RabbitMQ
- **Versioned presets** - Each preset has a version; rollback on conflict
- **Conflict resolution** - Last-write-wins with audit trail

## Monitoring
- Track `active_preset` changes in analytics
- Alert on unexpected `active_preset` switches
- Log all preset creation/deletion events

## Owner
Backend Team
Priority: High