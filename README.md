# Neovi Site BOM

Neovi Site BOM is a standalone internal application for turning project data
into an approved purchasing and site-kit list.

This project lives separately from Load Manager and the Factory Floor website.
It can exchange data with both systems through documented APIs and files.

## What It Does

1. Import a versioned project JSON file from Revit or another approved source.
2. Match project materials to the company catalog.
3. Calculate required, stock, already ordered, and final order quantities.
4. Organize material by construction phase and site kit.
5. Flag missing specifications or uncertain matches.
6. Approve a revision and retain its history.
7. Export purchasing, kit, and wall-load information.

## Main Screen

The project screen will contain:

- Overview
- Foundation and Substructure
- Floor and Wall Assembly
- Roof and Close-In
- Kits and Wall Loads
- Issues

Each BOM line will show:

| Item | Design | Overage | Stock | Ordered | Final Order | Status |
|---|---:|---:|---:|---:|---:|---|
| Connecting Rod | 100 | 10 | 5 | 0 | 105 | Needs review |

Manual changes require a short reason and are saved in the revision history.

## Data and Google Sheets

The application database is the source of truth. It stores projects, catalog
items, revisions, quantities, approvals, kits, and change history.

After a revision is approved, the application updates a company Google Sheet.
The Sheet is the current shared view for purchasing and field teams, but it is
not the calculation engine.

```text
Project JSON
    -> Site BOM calculation
    -> Review and approval
    -> Application database
    -> Updated Google Sheet and CSV exports
```

CSV files are import/export snapshots. They are not used as the live database.

## Quantity Calculation

```text
required = ceil(design quantity x (1 + overage))
needed   = max(0, required + target stock - on-hand - already ordered)
order    = needed rounded to the vendor pack or minimum order quantity
```

The calculation and its inputs remain visible on every BOM line.

## Languages

| Language | Use |
|---|---|
| TypeScript | Frontend, API, validation, calculations, and integrations |
| SQL | Application data and revision history |
| HTML/CSS | User interface and printable views |
| Python | Optional connection to the existing wall-load planner |

## Tools and Libraries

| Tool | Use |
|---|---|
| React and Vite | Web interface |
| Express | Backend API |
| Zod | Import and API validation |
| SQLite with `better-sqlite3` | Primary application database |
| Google Sheets API | Publish the latest approved BOM |
| Google authentication libraries | Secure server-to-server Sheet access |
| Vitest | Calculation and API tests |
| GitHub | Source control and reviews |
| Cloudflare Tunnel | Secure access to the deployed internal service |

Cloudflare D1 can replace SQLite if the application is later moved entirely to
Cloudflare Workers.

## Repository Layout

```text
frontend/                 React application
backend/                  API, database, calculations, and exports
shared/                   Shared types and validation schemas
integrations/
  google-sheets/          Approved BOM publishing
  load-manager/           Wall-load request and result exchange
docs/                     Import contract and operating notes
```

## First Version

- Project JSON import
- Controlled material catalog
- Quantity calculations with visible inputs
- Draft, approved, and superseded revisions
- Manual changes with reasons
- Purchasing and kit CSV exports
- One-way Google Sheets publishing after approval
- Wall-load file exchange with Load Manager

## Inputs Needed

- One real project JSON export
- Approved material catalog and units
- Current quantity and overage rules
- Vendor pack sizes and minimum orders
- Google Sheet ID and service-account access
- Confirmed wall-load exchange format
