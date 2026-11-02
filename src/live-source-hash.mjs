import { createHash } from 'node:crypto';

// Hash exactly the source fields applied by the Apps Script merger. The
// generated HTML also contains timestamps and document lists, which must not
// create a new Sheet revision when the BOM items are unchanged.
function stableJson(value) {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(',')}}`;
  }
  const json = JSON.stringify(value);
  if (json === undefined) throw new TypeError('Source payload contains a non-JSON value');
  return json;
}

export function sourceItemsHash(items) {
  if (!Array.isArray(items)) throw new TypeError('Source items must be an array');
  return createHash('sha256').update(stableJson({ items })).digest('hex');
}
