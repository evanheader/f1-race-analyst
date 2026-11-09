import { useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from 'recharts'
import type { Lap, RaceResult } from '../api'
import { formatClock, formatLapTime } from '../format'
import { buildChartData, type LapChartMode } from '../lapChart'
import { teamColor } from '../teamColors'

const AXIS = { stroke: 'transparent', tick: { fill: '#9AA6BC', fontSize: 12 }, tickLine: false } as const

interface Series {
  key: string
  code: string
  color: string
  dashed: boolean
}

function ChartTooltip({ active, label, payload, series }: TooltipContentProps<number, string> & { series: Series[] }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-line-strong bg-raised/95 px-3 py-2 text-sm shadow-xl backdrop-blur">
      <p className="mb-1 text-[0.8125rem] text-muted">Lap {label}</p>
      {series.map((s) => {
        const value = payload.find((p) => p.dataKey === s.key)?.value
        // A bridged point is drawn to join the line, but it is not a lap anyone drove at that time.
        if (typeof value !== 'number' || payload[0]?.payload?.[`i${s.key.slice(1)}`]) return null
        return (
          <p key={s.key} className="flex items-center gap-2">
            <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            <span className="num w-9">{s.code}</span>
            <span className="num">{formatLapTime(value)}</span>
          </p>
        )
      })}
    </div>
  )
}

/** Lap times of the drivers picked in the classification. Clean shows racing pace; raw shows every timed lap. */
export default function LapChart({ laps, chosen }: { laps: Lap[]; chosen: RaceResult[] }) {
  const [mode, setMode] = useState<LapChartMode>('clean')
  const data = buildChartData(
    laps,
    chosen.map((r) => r.driver_id),
    mode,
  )
  // A second driver from the same team gets a dashed line in the same color.
  const seenTeams = new Set<string>()
  const series: Series[] = chosen.map((r) => {
    const dashed = seenTeams.has(r.team)
    seenTeams.add(r.team)
    return { key: `d${r.driver_id}`, code: r.driver_code ?? r.driver_name, color: teamColor(r.team), dashed }
  })

  return (
    <section aria-labelledby="lap-chart-heading" className="panel p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="lap-chart-heading" className="heading">
          Lap times
        </h2>
        <div role="group" aria-label="Laps to show" className="segmented">
          {(['clean', 'raw'] as const).map((m) => (
            <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}>
              {m === 'clean' ? 'Clean' : 'Raw'}
            </button>
          ))}
        </div>
      </div>

      <ul aria-label="Drivers on the chart" className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <svg aria-hidden="true" viewBox="0 0 18 4" className="h-1 w-[18px]">
              <line x1="0" y1="2" x2="18" y2="2" stroke={s.color} strokeWidth="3" strokeDasharray={s.dashed ? '5 3' : undefined} />
            </svg>
            <span className="num">{s.code}</span>
          </li>
        ))}
        {series.length === 0 && <li className="text-muted">Pick drivers in the classification to compare them.</li>}
      </ul>

      {data === null ? (
        series.length > 0 && <p className="mt-4 text-muted">No laps to plot for these drivers.</p>
      ) : (
        <div className="-ml-2 mt-3">
          <ResponsiveContainer width="100%" height={340} initialDimension={{ width: 800, height: 340 }}>
            <LineChart data={data.rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <pattern id="slow-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="6" height="6" fill="rgb(255 255 255 / 0.03)" />
                  <line x1="0" y1="0" x2="0" y2="6" stroke="rgb(255 255 255 / 0.08)" strokeWidth="2" />
                </pattern>
              </defs>
              <CartesianGrid stroke="rgb(255 255 255 / 0.06)" vertical={false} />
              {data.slowRanges.map(([first, last]) => (
                <ReferenceArea key={first} x1={first - 0.5} x2={last + 0.5} fill="url(#slow-hatch)" strokeOpacity={0} ifOverflow="hidden" />
              ))}
              <XAxis dataKey="lap" type="number" domain={[data.firstLap, data.lastLap]} allowDecimals={false} {...AXIS} />
              <YAxis
                type="number"
                domain={[data.yMin, data.yMax]}
                allowDataOverflow
                width={48}
                tickFormatter={(v: number) => formatClock(v)}
                {...AXIS}
              />
              <Tooltip
                cursor={{ stroke: 'rgb(255 255 255 / 0.25)', strokeWidth: 1 }}
                content={(props) => <ChartTooltip {...props} series={series} />}
              />
              {series.map((s) => (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  name={s.code}
                  type={mode === 'clean' ? 'monotone' : 'linear'}
                  stroke={s.color}
                  strokeDasharray={s.dashed ? '6 4' : undefined}
                  strokeWidth={mode === 'clean' ? 2.25 : 1.5}
                  dot={mode === 'raw' ? { r: 1.6, strokeWidth: 0, fill: s.color } : false}
                  activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="mt-2 max-w-prose text-[0.8125rem] text-muted">
        {mode === 'clean'
          ? `Racing laps only: pit laps, deleted laps, safety car laps and laps outside 107% of each driver's typical lap are left out${
              data && data.hidden > 0 ? ` (${data.hidden} here)` : ''
            }. Gaps of up to 3 laps are joined with a straight line. Switch to raw to see every lap.`
          : 'Every timed lap as recorded, pit laps and deleted laps included.'}
        {data !== null && data.slowRanges.length > 0 && ' Hatched laps were slow for the whole field: safety car, red flag or rain.'}
      </p>
    </section>
  )
}
