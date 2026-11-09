// Builds src/data/circuits.json: for each of our circuit_ref values, its country and an SVG outline.
// Outlines come from https://github.com/bacinger/f1-circuits (MIT), pinned to one commit.
// Run with `npm run gen:circuits`. The output is checked in, so the site needs no network at build time.
import { writeFile } from 'node:fs/promises'

const SHA = '8094e957b8d6aa8b9f4510c93968556cccd30e02'
const DATA_URL = `https://raw.githubusercontent.com/bacinger/f1-circuits/${SHA}/f1-circuits.geojson`
const OUT = new URL('../src/data/circuits.json', import.meta.url)

// circuit_ref -> [ISO 3166-1 alpha-2 country, dataset id or null].
// The dataset holds one layout per circuit, so there is no layout to choose.
// null means the dataset has no outline: Fuji, Buddh, Valencia and Yeongam are not in it,
// and for Indianapolis it only has the oval, not the road course Formula 1 used.
const CIRCUITS = {
  albert_park: ['au', 'au-1953'],
  americas: ['us', 'us-2012'],
  bahrain: ['bh', 'bh-2002'],
  baku: ['az', 'az-2016'],
  buddh: ['in', null],
  catalunya: ['es', 'es-1991'],
  fuji: ['jp', null],
  hockenheimring: ['de', 'de-1932'],
  hungaroring: ['hu', 'hu-1986'],
  imola: ['it', 'it-1953'],
  indianapolis: ['us', null],
  interlagos: ['br', 'br-1940'],
  istanbul: ['tr', 'tr-2005'],
  jeddah: ['sa', 'sa-2021'],
  losail: ['qa', 'qa-2004'],
  madring: ['es', 'es-2026'],
  magny_cours: ['fr', 'fr-1960'],
  marina_bay: ['sg', 'sg-2008'],
  miami: ['us', 'us-2022'],
  monaco: ['mc', 'mc-1929'],
  monza: ['it', 'it-1922'],
  mugello: ['it', 'it-1914'],
  nurburgring: ['de', 'de-1927'],
  portimao: ['pt', 'pt-2008'],
  red_bull_ring: ['at', 'at-1969'],
  ricard: ['fr', 'fr-1969'],
  rodriguez: ['mx', 'mx-1962'],
  sepang: ['my', 'my-1999'],
  shanghai: ['cn', 'cn-2004'],
  silverstone: ['gb', 'gb-1948'],
  sochi: ['ru', 'ru-2014'],
  spa: ['be', 'be-1925'],
  suzuka: ['jp', 'jp-1962'],
  valencia: ['es', null],
  vegas: ['us', 'us-2023'],
  villeneuve: ['ca', 'ca-1978'],
  yas_marina: ['ae', 'ae-2009'],
  yeongam: ['kr', null],
  zandvoort: ['nl', 'nl-1948'],
}

const SIZE = 100
const MARGIN = 4
const TOLERANCE = 0.2 // in viewBox units; drops points that barely change the line

/** Perpendicular distance from point p to the line through a and b. */
function distance(p, a, b) {
  const dx = b[0] - a[0]
  const dy = b[1] - a[1]
  const len = Math.hypot(dx, dy)
  if (len === 0) return Math.hypot(p[0] - a[0], p[1] - a[1])
  return Math.abs(dy * p[0] - dx * p[1] + b[0] * a[1] - b[1] * a[0]) / len
}

/** Douglas-Peucker line simplification. */
function simplify(points, tolerance) {
  if (points.length < 3) return points
  let worst = 0
  let index = 0
  for (let i = 1; i < points.length - 1; i++) {
    const d = distance(points[i], points[0], points.at(-1))
    if (d > worst) {
      worst = d
      index = i
    }
  }
  if (worst <= tolerance) return [points[0], points.at(-1)]
  return [
    ...simplify(points.slice(0, index + 1), tolerance).slice(0, -1),
    ...simplify(points.slice(index), tolerance),
  ]
}

/** Longitude and latitude to a path in a 0..100 box, keeping the aspect ratio and centering. */
function toPath(coordinates) {
  const meanLat = coordinates.reduce((sum, c) => sum + c[1], 0) / coordinates.length
  const scaleX = Math.cos((meanLat * Math.PI) / 180)
  const flat = coordinates.map(([lon, lat]) => [lon * scaleX, -lat])
  const xs = flat.map((p) => p[0])
  const ys = flat.map((p) => p[1])
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  const width = Math.max(...xs) - minX
  const height = Math.max(...ys) - minY
  const scale = (SIZE - 2 * MARGIN) / Math.max(width, height)
  const offsetX = (SIZE - width * scale) / 2
  const offsetY = (SIZE - height * scale) / 2
  const points = flat.map(([x, y]) => [(x - minX) * scale + offsetX, (y - minY) * scale + offsetY])
  const closed = Math.hypot(points[0][0] - points.at(-1)[0], points[0][1] - points.at(-1)[1]) < 1.5
  const kept = simplify(points, TOLERANCE)
  const round = (n) => Math.round(n * 10) / 10
  const body = kept.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${round(x)} ${round(y)}`).join('')
  return closed ? `${body}Z` : body
}

const response = await fetch(DATA_URL)
if (!response.ok) throw new Error(`Could not download the circuits: ${response.status}`)
const features = new Map((await response.json()).features.map((f) => [f.properties.id, f]))

const output = {}
for (const [ref, [country, id]] of Object.entries(CIRCUITS)) {
  let path = null
  if (id !== null) {
    const feature = features.get(id)
    if (!feature) throw new Error(`${ref}: ${id} is not in the dataset`)
    path = toPath(feature.geometry.coordinates)
  }
  output[ref] = { country, path }
}

await writeFile(OUT, `${JSON.stringify(output, null, 1)}\n`)
console.log(`Wrote ${Object.keys(output).length} circuits to src/data/circuits.json`)
