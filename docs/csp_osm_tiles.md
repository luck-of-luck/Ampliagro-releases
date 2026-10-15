# CSP Connect-Src Issue - OSM Tiles in Service Worker

## Problem
OpenStreetMap tiles (`*.tile.openstreetmap.org`) are not loading correctly in the PWA Service Worker due to CSP restrictions.

## Current CSP Configuration (base.py:432-450)
```
connect-src: 'self', 'api.open-meteo.com', 'servicodados.ibge.gov.br', 
              'nominatim.openstreetmap.org', '*.tile.openstreetmap.org', 
              '*.ingest.sentry.io', 'huggingface.co', '*.huggingface.co', 
              'esm.run'
```

## Root Cause
While `*.tile.openstreetmap.org` is listed in `connect-src`, the Service Worker (`sw.js`) may not be applying the CSP correctly, or there could be a version mismatch between the CSP definition and the SW implementation.

## Solution Steps
1. **Verify CSP in base.py** - Confirm `*.tile.openstreetmap.org` is present in `connect-src`
2. **Update sw.js** - Ensure the Service Worker respects the CSP directives
3. **Test in staging** - Verify map loads with correct tile sources
4. **Monitor logs** - Check for CSP-related errors in console

## Verification
- Check `CSP_LOCK` in base.py includes `*.tile.openstreetmap.org`
- Review `sw.js` for `fetch()` calls targeting OSM tiles
- Ensure no hardcoded `*` wildcards that bypass CSP
- Test with Chrome DevTools -> Security tab -> CSP

## Related Issues
- #unknown - CSP connect-src OSM tiles unresolved
- #unknown - Map not loading tiles in PWA mode

## Owner
Backend/Frontend Integration Team
Priority: High