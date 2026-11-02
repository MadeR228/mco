import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Loading } from './components/ui.jsx'
import Layout from './components/Layout.jsx'
import ComparePage from './pages/ComparePage.jsx'
import ContinuousPage from './pages/ContinuousPage.jsx'
import CriteriaPage from './pages/CriteriaPage.jsx'
import DataPage from './pages/DataPage.jsx'
import LimitsPage from './pages/LimitsPage.jsx'
import SensitivityPage from './pages/SensitivityPage.jsx'
import SolutionPage from './pages/SolutionPage.jsx'
import { ContinuousProvider } from './state/continuous.jsx'
import { MetaProvider } from './state/meta.jsx'
import { ProblemProvider } from './state/problem.jsx'

// Довідка тягне react-markdown – завантажується окремим фрагментом лише при відкритті
const HelpPage = lazy(() => import('./pages/HelpPage.jsx'))

export default function App() {
  return (
    <MetaProvider>
      <ProblemProvider>
        <ContinuousProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<Navigate to="/discrete/data" replace />} />
                <Route path="discrete" element={<Navigate to="/discrete/data" replace />} />
                <Route path="discrete/data" element={<DataPage />} />
                <Route path="discrete/criteria" element={<CriteriaPage />} />
                <Route path="discrete/limits" element={<LimitsPage />} />
                <Route path="discrete/solution" element={<SolutionPage />} />
                <Route path="discrete/compare" element={<ComparePage />} />
                <Route path="discrete/sensitivity" element={<SensitivityPage />} />
                <Route path="continuous" element={<ContinuousPage />} />
                <Route path="help" element={<Suspense fallback={<Loading>Завантажую…</Loading>}><HelpPage /></Suspense>} />
                <Route path="*" element={<Navigate to="/discrete/data" replace />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </ContinuousProvider>
      </ProblemProvider>
    </MetaProvider>
  )
}
