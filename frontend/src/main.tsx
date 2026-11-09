import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { ApiError } from './api'
import App from './App'
import './index.css'
import { applyTheme, loadThemeId } from './themes'

applyTheme(loadThemeId())

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // A missing race stays missing, so only retry network errors and server errors.
      retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status < 500),
      refetchOnWindowFocus: false,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
