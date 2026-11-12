import { mkdir, copyFile } from 'node:fs/promises';
const destination = new URL('../public/saved-results/', import.meta.url);
await mkdir(destination, { recursive: true });
for (const n of [8, 12, 16]) {
  await copyFile(new URL(`../../data/results/result_sector_${n}.json`, import.meta.url), new URL(`result_sector_${n}.json`, destination));
}
