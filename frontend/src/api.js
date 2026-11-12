import { validateResult } from './data.js';
const BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/$/, '');
async function responseJSON(response) {
  let data;
  try { data = await response.json(); } catch { throw new Error(`Server returned non-JSON data (${response.status}). Check the API URL.`); }
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data);
    throw new Error(`${response.status}: ${detail}`);
  }
  return data;
}
export async function loadResult(instance, signal) {
  return validateResult(await responseJSON(await fetch(`/saved-results/result_${instance}.json`, { signal })));
}
export async function runOptimization(payload, signal) {
  return validateResult(await responseJSON(await fetch(`${BASE}/optimize`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  })));
}
export async function health(signal) {
  return responseJSON(await fetch(`${BASE}/health`, { signal }));
}
