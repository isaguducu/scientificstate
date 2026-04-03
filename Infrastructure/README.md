# Infrastructure

Backend infrastructure for ScientificState Module Store.

## Supabase Setup

1. Create a Supabase project (or use existing).
2. Run the migration:
   ```bash
   psql "$SUPABASE_DB_URL" -f supabase/migrations/001_module_registry.sql
   ```
3. RLS is enabled by default — public read, authenticated write.

## Cloudflare R2 Setup

1. Install Wrangler: `npm install -g wrangler`
2. Authenticate: `wrangler login`
3. Create the bucket:
   ```bash
   wrangler r2 bucket create scientificstate-modules
   ```
4. Deploy config: `cd cloudflare && wrangler deploy`

Module tarballs are stored in R2 at `{domain_id}/{version}/package.tar.gz`.
Manifests are stored at `{domain_id}/{version}/manifest.json`.
