import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import Ajv2020 from 'ajv/dist/2020';
import schema from '../types/snapshot.schema.json';
import { SNAPSHOT_KEYS, type Snapshot } from '../types/contract';

const snap = JSON.parse(readFileSync(resolve(process.cwd(), 'public/data/snapshot.json'), 'utf-8')) as Snapshot;

describe('snapshot contract', () => {
  it('validates against the schema generated from the Pydantic models', () => {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    const ok = ajv.validate(schema, snap);
    expect(ajv.errors ?? []).toEqual([]);
    expect(ok).toBe(true);
  });
  it('TypeScript contract keys match the schema', () => {
    expect([...SNAPSHOT_KEYS].sort()).toEqual(Object.keys((schema as { properties: object }).properties).sort());
  });
  it('carries run id, timestamp and sources', () => {
    expect(snap.pipeline_run_id).toBeTruthy();
    expect(snap.generated_at).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    expect(snap.sources.length).toBeGreaterThan(3);
  });
});
