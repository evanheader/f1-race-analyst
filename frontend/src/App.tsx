import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'
import Layout from './components/Layout'
import { Loading } from './components/Status'
import AskPage from './pages/AskPage'
import NotFoundPage from './pages/NotFoundPage'
import RaceListPage from './pages/RaceListPage'
import { loadRacePage } from './queries'

// The race page carries the charting library, so it loads only when someone opens a race
// (or hovers a race card, which starts the download early).
const RaceDetailPage = lazy(loadRacePage)

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<RaceListPage />} />
        <Route
          path="races/:id"
          element={
            <Suspense fallback={<Loading what="the race" />}>
              <RaceDetailPage />
            </Suspense>
          }
        />
        <Route path="ask" element={<AskPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
